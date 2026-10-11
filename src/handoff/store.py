"""Ticket state on disk. A file dropped into the inbox becomes a ticket folder under RUNS:

<RUNS>/<id>/ticket.md     the ticket text (answers to questions are appended)
<RUNS>/<id>/state.json    current state: stage, plan, review, diff, ...
<RUNS>/<id>/events.jsonl  live feed, append-only, streamed to the UI
"""
import json
import re
import threading
import time
from pathlib import Path

from . import settings

ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
ACTIVE = ("triage", "coding", "checking", "review", "delivering")


def path(tid: str) -> Path:
    return settings.RUNS / tid


def load(tid: str) -> dict:
    return json.loads((path(tid) / "state.json").read_text())


def save(t: dict) -> None:
    # shortcut: no lock around load-change-save, so two threads changing one ticket at the same moment can
    # lose one change; add a lock if the API, the worker and the Jira poller start to collide
    t["updated"] = time.time()
    f = path(t["id"]) / "state.json"
    tmp = f.with_name(f"state.{threading.get_ident()}.tmp")  # one temp file per thread
    tmp.write_text(json.dumps(t, ensure_ascii=False, indent=2), errors="replace")
    tmp.replace(f)  # atomic: readers never see a half-written file


def all_tickets() -> list[dict]:
    tickets = []
    for f in settings.RUNS.glob("*/state.json"):
        try:
            tickets.append(json.loads(f.read_text()))
        except (OSError, ValueError):
            continue  # removed or damaged: one bad ticket must not hide the others
    return sorted(tickets, key=lambda t: t["created"])


def text(t: dict) -> str:
    return (path(t["id"]) / "ticket.md").read_text()


def emit(t: dict, kind: str, **fields) -> None:
    """Append an event to the ticket's live feed."""
    event = {"ts": time.time(), "stage": t["stage"], "kind": kind, **fields}
    # errors="replace": agent output can carry lone surrogates, which UTF-8 cannot encode
    with open(path(t["id"]) / "events.jsonl", "a", encoding="utf-8", errors="replace") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def log(t: dict, msg: str) -> None:
    emit(t, "info", msg=msg)


def move(t: dict, stage: str, msg: str) -> None:
    t["stage"] = stage
    t["since"] = time.time()
    save(t)
    emit(t, "stage", msg=msg)


def front_matter(body: str) -> dict[str, str]:
    """The `key: value` lines between the `---` lines at the top of a ticket."""
    lines = body.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return meta
        key, _, value = line.partition(":")
        meta[key.strip().lower()] = value.split(" #")[0].strip()  # " #" starts a comment, as in YAML
    return {}  # an unclosed block is not front matter


def create(name: str, body: str, check, origin: str, **extra) -> dict:
    """A new ticket from its text. If check(t) returns an error, the ticket fails at once instead of queueing."""
    base = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-") or "ticket"
    tid, n = base, 1
    while path(tid).exists():
        n += 1
        tid = f"{base}-{n}"
    path(tid).mkdir(parents=True)
    (path(tid) / "ticket.md").write_text(body)
    title = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), tid)
    now = time.time()
    t = {"id": tid, "title": title, "project": front_matter(body).get("project", ""),
         "stage": "queued", "created": now, "since": now, "round": 0, **extra}
    if err := check(t):
        t.update(stage="failed", failed_stage="triage", error=err)
    save(t)
    emit(t, "stage", msg=f"{origin} rejected at intake: {err}" if err else f"{origin} queued")
    return t


def ingest_inbox(check) -> None:
    """Turn the .md files in the inbox into tickets."""
    for f in sorted(settings.INBOX.glob("*.md")):
        st = f.stat()
        if f.name.startswith(".") or not st.st_size or time.time() - st.st_mtime < 2:
            continue  # hidden, empty (a new file in an editor), or maybe still being written
        create(f.stem, f.read_text(encoding="utf-8-sig", errors="replace"), check, f.name)  # -sig drops a BOM
        f.unlink()


def requeue(t: dict, msg: str) -> None:
    """Queue a failed or rejected ticket again, with a fresh token budget."""
    for k in ("sessions", "tokens"):
        t.pop(k, None)
    move(t, "queued", msg)


def requeue_interrupted() -> None:
    for t in all_tickets():
        if t["stage"] in ACTIVE:
            move(t, "queued", "Server restarted, ticket re-queued")


def answer(t: dict, reply: str) -> None:
    """Append the person's answer to the ticket text and queue it for triage again."""
    questions = "\n".join(f"- {q}" for q in t.get("questions", []))
    with open(path(t["id"]) / "ticket.md", "a") as f:
        f.write(f"\n\n## Q&A\n\nQuestions:\n{questions}\n\nAnswer:\n{reply.strip()}\n")
    t["questions"] = []
    move(t, "queued", "Answer added, ticket re-queued")
