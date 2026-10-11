"""Jira Cloud as a ticket source (config.toml [jira], off by default).

Issues that match the JQL become tickets, with the issue key as the ticket id. The outcome goes back to the
issue as a comment and one of the LABELS. To answer questions or try again, a person comments on the issue
and removes that label; the next poll reads the issue again and queues it. The API token comes from the
JIRA_TOKEN environment variable, never from config.toml.
"""
import base64
import os
import threading
import traceback

from .. import store
from . import rest

LABELS = {"question": "handoff-question", "rejected": "handoff-rejected",
          "failed": "handoff-failed", "done": "handoff-done"}


def _call(cfg: dict, method: str, path: str, body=None):
    token = os.environ.get("JIRA_TOKEN")
    if not token:
        raise RuntimeError("Jira is enabled in config.toml, but JIRA_TOKEN is not set")
    auth = base64.b64encode(f"{cfg['email']}:{token}".encode()).decode()
    return rest.request(method, cfg["url"].rstrip("/") + path, {"Authorization": f"Basic {auth}"}, body)


def text(node) -> str:
    """Atlassian Document Format (descriptions, comments) as markdown-like plain text."""
    if not node:
        return ""
    kind, kids = node.get("type"), node.get("content") or []
    inner = "".join(text(k) for k in kids)
    attrs = node.get("attrs") or {}
    if kind == "text":
        t = node.get("text", "")
        return f"`{t}`" if any(m.get("type") == "code" for m in node.get("marks") or []) else t
    if kind == "hardBreak":
        return "\n"
    if kind == "paragraph":
        return inner + "\n\n"
    if kind == "heading":
        return "#" * attrs.get("level", 2) + " " + inner + "\n\n"
    if kind == "codeBlock":
        return f"```\n{inner}\n```\n\n"
    if kind == "bulletList":
        return "".join(f"- {text(k).strip()}\n" for k in kids) + "\n"
    if kind == "orderedList":
        return "".join(f"{i}. {text(k).strip()}\n" for i, k in enumerate(kids, 1)) + "\n"
    if kind == "mention":
        return attrs.get("text", "")
    if kind in ("inlineCard", "blockCard"):
        return attrs.get("url", "")
    return inner  # doc, listItem, blockquote, panel, table, ...


def adf(s: str) -> dict:
    """Plain text as an Atlassian Document: blank lines split paragraphs, other newlines become line breaks."""
    paragraphs = []
    for block in s.strip().split("\n\n"):
        content = []
        for i, line in enumerate(block.split("\n")):
            if i:
                content.append({"type": "hardBreak"})
            if line:  # ADF rejects empty text nodes
                content.append({"type": "text", "text": line})
        paragraphs.append({"type": "paragraph", "content": content})
    return {"type": "doc", "version": 1, "content": paragraphs}


def ticket_text(cfg: dict, issue: dict, me: str) -> str:
    """The ticket file for an issue: summary, description and the comments, ours included (they hold the questions)."""
    f = issue["fields"]
    project = (cfg.get("projects") or {}).get(f["project"]["key"], "")
    # shortcut: the first 100 comments; page with startAt if tickets ever carry longer discussions
    comments = _call(cfg, "GET", f"/rest/api/3/issue/{issue['key']}/comment?orderBy=created&maxResults=100")
    parts = [f"---\nproject: {project}\n---\n", f"# {f['summary']}\n", text(f.get("description")).strip()]
    if comments.get("comments"):
        parts.append("\n## Comments\n")
        for c in comments["comments"]:
            who = "handoff" if c["author"]["accountId"] == me else c["author"].get("displayName", "Someone")
            parts.append(f"**{who}** ({c['created'][:10]}):\n\n{text(c['body']).strip()}\n")
    return "\n".join(parts) + "\n"


def report(cfg: dict, t: dict) -> None:
    """Tell the issue how the ticket ended: a comment, and our label for that outcome."""
    stage, label = t["stage"], LABELS[t["stage"]]
    error = (t.get("error") or "unknown error").splitlines()[0]
    questions = "\n".join(f"{i}. {q}" for i, q in enumerate(t.get("questions") or [], 1))
    msg = {
        "question": f"handoff has questions before it can start:\n\n{questions}\n\n"
                    f"Answer them in a comment, then remove the label {label}.",
        "rejected": f"handoff did not take this ticket:\n\n{(t.get('triage') or {}).get('summary') or error}\n\n"
                    f"Change the ticket, then remove the label {label} to try again.",
        "failed": f"handoff stopped: {error}\n\nRemove the label {label} to try again.",
        "done": "handoff is done. " + (f"Merge request: {t['mr']}" if t.get("mr") else f"Branch: {t.get('branch')}"),
    }[stage]
    _call(cfg, "POST", f"/rest/api/3/issue/{t['jira']}/comment", {"body": adf(msg)})
    ops = [{"add": label}] + [{"remove": other} for other in LABELS.values() if other != label]
    _call(cfg, "PUT", f"/rest/api/3/issue/{t['jira']}", {"update": {"labels": ops}})


def poll(cfg: dict, check) -> None:
    me = _call(cfg, "GET", "/rest/api/3/myself")["accountId"]
    # issues that wait on a person carry one of our labels and stay out of the search
    jql = f"({cfg['jql']}) AND (labels IS EMPTY OR labels NOT IN ({', '.join(LABELS.values())}))"
    issues, page = [], {}
    while True:
        page = _call(cfg, "POST", "/rest/api/3/search/jql",
                     {"jql": jql, "fields": ["summary", "description", "project", "labels"], "maxResults": 50,
                      **({"nextPageToken": page["nextPageToken"]} if page.get("nextPageToken") else {})})
        issues += page.get("issues", [])
        if not page.get("nextPageToken"):
            break
    for issue in issues:
        key, labels = issue["key"], set(issue["fields"].get("labels") or [])
        if not store.ID_RE.match(key):
            continue
        if not store.path(key).exists():
            if not labels & set(LABELS.values()):  # an issue we already handled (runs/ was cleared) stays alone
                store.create(key, ticket_text(cfg, issue, me), check, f"Jira {key}", jira=key)
            continue
        stage = store.load(key)["stage"]
        # after a question, rejection or failure was reported, the person removed our label: read the issue again
        if stage in ("question", "rejected", "failed") and store.load(key).get("jira_reported") == stage \
                and LABELS[stage] not in labels:
            body = ticket_text(cfg, issue, me)
            t = store.load(key)  # fresh: someone may have used the UI during the call
            if t["stage"] == stage:
                (store.path(key) / "ticket.md").write_text(body)
                if stage == "question":  # an answer continues the same attempt, with the same token budget
                    store.move(t, "queued", "Answered in Jira, ticket re-queued")
                else:
                    store.requeue(t, "Re-queued from Jira")
    for t in store.all_tickets():
        if t.get("jira") and t["stage"] in LABELS and t.get("jira_reported") != t["stage"]:
            report(cfg, t)
            cur = store.load(t["id"])  # fresh: someone may have used the UI during the call
            if cur["stage"] == t["stage"]:
                cur["jira_reported"] = t["stage"]
                store.save(cur)


def loop(stop: threading.Event, cfg: dict, check) -> None:
    while not stop.is_set():
        try:
            poll(cfg, check)
        except Exception:
            traceback.print_exc()  # Jira down or misconfigured: try again on the next poll
        stop.wait(cfg.get("poll_seconds", 60))
