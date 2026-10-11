"""The pipeline's flow with fake agents: triage, the coding rounds, delivery, a restart, and what is left behind.

Setup and checks are real commands in the sandbox, so this needs bubblewrap.
"""
import shutil
import threading

import pytest

from handoff import agent, pipeline, repo, settings, store

pytestmark = pytest.mark.skipif(shutil.which("bwrap") is None, reason="bubblewrap is not installed")
TICKET = "---\nproject: p\n---\n# Add b\n\nAdd b.txt.\n"


@pytest.fixture
def project(runs, tmp_path, monkeypatch):
    """Project `p`: a repository with one commit on main, whose setup and checks pass."""
    monkeypatch.setattr(settings, "PROJECTS", tmp_path / "projects")
    r = settings.PROJECTS / "p"
    r.mkdir(parents=True)
    repo.git(r, "init", "-q", "-b", "main")
    (r / "a.txt").write_text("a\n")
    repo.git(r, "add", "-A")
    repo.git(r, *repo.BOT, "commit", "-qm", "base")
    monkeypatch.setitem(pipeline.CFG["projects"], "p",
                        {"base_branch": "main", "setup": "true", "check": ["true"], "allowed_bash": []})
    return r


def fake_agents(monkeypatch, decision: str = "go") -> dict:
    """Triage decides `decision`, coding writes b.txt, review approves. Returns what triage saw."""
    seen = {}

    def run(prompt, cwd, tools, *, schema=None, **kw):
        out = {"session_id": "s", "modelUsage": {}}
        if schema is pipeline.TRIAGE_SCHEMA:
            seen["a.txt"] = (cwd / "a.txt").read_text()
            questions = ["Which b?"] if decision == "question" else []
            return {**out, "structured_output": {"decision": decision, "summary": "-", "questions": questions,
                                                 "plan": "Add b.txt."}}
        if schema is pipeline.REVIEW_SCHEMA:
            return {**out, "structured_output": {"approved": True, "summary": "Fine.", "findings": []}}
        (cwd / "b.txt").write_text("b\n")
        return {**out, "result": "- Add b.txt"}

    monkeypatch.setattr(agent, "run", run)
    return seen


def test_a_ticket_ends_on_a_branch(project, monkeypatch):
    # a person checked out something else in the project: triage must still read the base branch
    repo.git(project, "checkout", "-q", "-b", "other")
    (project / "a.txt").write_text("changed\n")
    seen = fake_agents(monkeypatch)
    pipeline.run_ticket(store.create("T", TICKET, pipeline.project_error, "test"), threading.Event())

    t = store.load("T")
    assert t["stage"] == "done", t.get("error")
    assert seen["a.txt"] == "a\n", "triage read the checkout instead of the base branch"
    assert repo.git(project, "show", "handoff/T:b.txt").stdout == "b\n"
    assert not (store.path("T") / "wt").exists()


def test_a_restart_during_delivery_only_publishes(project, monkeypatch):
    fake_agents(monkeypatch)
    pipeline.run_ticket(store.create("T", TICKET, pipeline.project_error, "test"), threading.Event())
    # the server stopped while pushing to GitLab: on start the ticket is queued again, without failed_stage
    t = store.load("T")
    t["stage"] = "queued"
    store.save(t)
    monkeypatch.setattr(agent, "run", lambda *a, **kw: pytest.fail("the ticket ran from the start again"))

    pipeline.run_ticket(t, threading.Event())
    assert store.load("T")["stage"] == "done", store.load("T").get("error")


@pytest.mark.parametrize(("decision", "check", "stage"), [("question", "true", "question"), ("go", "false", "failed")])
def test_a_stopped_ticket_leaves_no_worktree(project, monkeypatch, decision, check, stage):
    fake_agents(monkeypatch, decision)
    monkeypatch.setitem(pipeline.CFG["projects"]["p"], "check", [check])
    pipeline.run_ticket(store.create("T", TICKET, pipeline.project_error, "test"), threading.Event())

    assert store.load("T")["stage"] == stage
    assert not (store.path("T") / "wt").exists(), "the worktree and its packages were left behind"
    assert not repo.git(project, "branch", "--list", "handoff/T").stdout, "an empty ticket branch was left behind"
