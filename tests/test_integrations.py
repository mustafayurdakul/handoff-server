"""The Jira and GitLab clients against a small fake server, and a git push to a local bare repository."""
import base64
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from handoff import repo, store
from handoff.integrations import gitlab, jira

DESCRIPTION = {"type": "doc", "version": 1, "content": [
    {"type": "paragraph", "content": [{"type": "text", "text": "Sort by "},
                                      {"type": "text", "text": "createdAt", "marks": [{"type": "code"}]}]},
    {"type": "bulletList", "content": [{"type": "listItem", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "newest first"}]}]}]},
]}


def comment(account: str, name: str, words: str) -> dict:
    return {"author": {"accountId": account, "displayName": name}, "created": "2026-10-10T01:02:03.000+0000",
            "body": {"type": "doc", "version": 1,
                     "content": [{"type": "paragraph", "content": [{"type": "text", "text": words}]}]}}


class Fake(BaseHTTPRequestHandler):
    labels: dict[str, list[str]] = {}
    calls: list[tuple] = []

    def log_message(self, *_):
        pass

    def reply(self, body) -> None:
        self.send_response(200 if body is not None else 204)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode() if body is not None else b"")

    def handle_any(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n)) if n else None
        self.calls.append((self.command, self.path, self.headers, body))  # headers: case-insensitive
        p = self.path
        if p == "/rest/api/3/myself":
            return self.reply({"accountId": "bot"})
        if p == "/rest/api/3/search/jql":
            return self.reply({"issues": [
                {"key": k, "fields": {"summary": f"Sort {k}", "description": DESCRIPTION, "project": {"key": "DOC"},
                                      "labels": v}} for k, v in self.labels.items()]})
        if p.startswith("/rest/api/3/issue/DOC-1/comment") and self.command == "GET":
            return self.reply({"comments": [comment("bot", "handoff", "our own note"),
                                            comment("u1", "Ayse", "Use the created date, not the edit date.")]})
        if p == "/rest/api/3/issue/DOC-1/comment":
            return self.reply({"id": "1"})
        if p == "/rest/api/3/issue/DOC-1":
            for op in body["update"]["labels"]:
                if "add" in op and op["add"] not in self.labels["DOC-1"]:
                    self.labels["DOC-1"].append(op["add"])
                if "remove" in op and op["remove"] in self.labels["DOC-1"]:
                    self.labels["DOC-1"].remove(op["remove"])
            return self.reply(None)
        if p == "/api/v4/projects/demo%2Fdemo-app/merge_requests":
            return self.reply({"web_url": "https://gitlab.example.com/demo/demo-app/-/merge_requests/7"})
        self.send_error(404)

    do_GET = do_POST = do_PUT = handle_any


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv("JIRA_TOKEN", "jira-secret")
    monkeypatch.setenv("GITLAB_TOKEN", "gitlab-secret")
    Fake.labels = {"DOC-1": ["handoff"], "DOC-2": ["handoff", "handoff-done"]}
    Fake.calls = []
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_jira_intake_report_and_answer(server, runs):
    cfg = {"url": server, "email": "bot@example.com", "jql": "labels = handoff", "projects": {"DOC": "demo-app"}}

    # a new issue becomes a ticket; an issue that already carries our label is left alone
    jira.poll(cfg, lambda t: None)
    t = store.load("DOC-1")
    body = store.text(t)
    assert (t["jira"], t["project"], t["stage"]) == ("DOC-1", "demo-app", "queued")
    assert "# Sort DOC-1" in body and "Sort by `createdAt`" in body and "- newest first" in body
    assert "Use the created date" in body and "**handoff**" in body and "our own note" in body
    assert not store.path("DOC-2").exists(), "an issue with a handoff-done label was taken again"
    auth = next(h for _, p, h, _ in Fake.calls if p == "/rest/api/3/myself")["Authorization"]
    assert auth == "Basic " + base64.b64encode(b"bot@example.com:jira-secret").decode()

    # a question is reported once: a comment and the question label
    t.update(stage="question", questions=["Newest or oldest first by default?"])
    store.save(t)
    Fake.calls.clear()
    jira.poll(cfg, lambda t: None)
    posted = [b for m, p, _, b in Fake.calls if m == "POST" and p == "/rest/api/3/issue/DOC-1/comment"]
    assert len(posted) == 1 and "Newest or oldest" in json.dumps(posted[0])
    assert "handoff-question" in Fake.labels["DOC-1"]
    jql = next(b for _, p, _, b in Fake.calls if p == "/rest/api/3/search/jql")["jql"]
    assert "NOT IN (handoff-question" in jql
    assert store.load("DOC-1")["jira_reported"] == "question"
    Fake.calls.clear()
    jira.poll(cfg, lambda t: None)
    assert not [c for c in Fake.calls if c[0] in ("POST", "PUT") and "/comment" in c[1]], "reported twice"
    assert store.load("DOC-1")["stage"] == "question", "queued again while the label is still there"

    # the person answers and removes the label: the ticket is read again and queued
    Fake.labels["DOC-1"].remove("handoff-question")
    jira.poll(cfg, lambda t: None)
    assert store.load("DOC-1")["stage"] == "queued"



def test_jira_one_broken_issue_does_not_stop_the_others(server, runs):
    cfg = {"url": server, "email": "bot@example.com", "jql": "labels = handoff", "projects": {"DOC": "demo-app"}}
    # an older ticket whose issue was deleted in Jira: reporting it gets HTTP 404 on every poll
    gone = store.create("DOC-9", "---\nproject: demo-app\n---\n# Gone\n", lambda t: None, "test", jira="DOC-9")
    gone.update(stage="failed", error="setup failed")
    store.save(gone)
    jira.poll(cfg, lambda t: None)
    t = store.load("DOC-1")
    t.update(stage="question", questions=["Newest or oldest first?"])
    store.save(t)

    jira.poll(cfg, lambda t: None)
    assert store.load("DOC-1")["jira_reported"] == "question", "the broken issue blocked the report"
    assert "jira_reported" not in store.load("DOC-9"), "a failed report counts as done"

def test_gitlab_merge_request(server):
    web = gitlab.open_mr(server, "gitlab-secret", "demo/demo-app", "handoff/DOC-1", "main", "DOC-1: Sort", "plan")
    assert web.endswith("/merge_requests/7")
    _, _, headers, mr = Fake.calls[-1]
    assert headers["PRIVATE-TOKEN"] == "gitlab-secret" and mr["source_branch"] == "handoff/DOC-1"


def test_gitlab_push(tmp_path):
    src, bare = tmp_path / "src", tmp_path / "bare.git"
    src.mkdir()
    repo.git(src, "init", "-q", "-b", "main")
    (src / "a.txt").write_text("a\n")
    repo.git(src, "add", "-A")
    repo.git(src, *repo.BOT, "commit", "-qm", "a")
    repo.git(src, "branch", "handoff/DOC-1")
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    gitlab.push(src, "handoff/DOC-1", str(bare), "gitlab-secret")
    assert repo.git(bare, "branch", "--list", "handoff/DOC-1").stdout
