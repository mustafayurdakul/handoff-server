"""The pipeline: runs queued tickets one at a time through triage, coding, checks, review and delivery."""
import re
import shlex
import threading
import traceback
from pathlib import Path
from string import Template

from . import agent, repo, sandbox, settings, store
from .integrations import gitlab

CFG = settings.CONFIG
READ_ONLY = ["Read", "Glob", "Grep"]
CODE_TOOLS = [*READ_ONLY, "Edit", "Write", "Bash"]
TAIL = 8000  # how much command output is kept and sent back to the coding agent

TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["go", "question", "reject"]},
        "summary": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "string"}},
        "plan": {"type": "string"},
    },
    "required": ["decision", "summary", "questions", "plan"],
}
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "approved": {"type": "boolean"},
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["blocker", "minor"]},
                    "file": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["severity", "file", "message"],
            },
        },
    },
    "required": ["approved", "summary", "findings"],
}
# results of an earlier attempt, cleared when a ticket runs again
ATTEMPT_KEYS = ("error", "failed_stage", "triage", "questions", "check", "diff", "tests", "review", "last_review",
                "work", "branch", "mr", "jira_reported")


# --- helpers ---------------------------------------------------------------------------------------------------

def prompt(name: str, **values: str) -> str:
    return Template((settings.PROMPTS / f"{name}.md").read_text()).safe_substitute(values)


def ask(t: dict, text: str, cwd: Path, tools: list[str], **kw) -> dict:
    """Run one agent step, add its token use to the ticket, and stop the ticket when it is over budget."""
    r = agent.run(text, cwd, tools, model=CFG["agent"]["model"], effort=CFG["agent"]["effort"],
                  timeout=CFG["limits"]["agent_minutes"] * 60, on_event=lambda e: store.emit(t, **e), **kw)
    usage = r.get("modelUsage") or {}
    # usage is cumulative per session, and --resume continues a session: keep each session's latest value, then sum
    t.setdefault("sessions", {})[r["session_id"]] = {
        "input": sum(u.get("inputTokens", 0) + u.get("cacheCreationInputTokens", 0) + u.get("cacheReadInputTokens", 0)
                     for u in usage.values()),
        "cache_read": sum(u.get("cacheReadInputTokens", 0) for u in usage.values()),
        "output": sum(u.get("outputTokens", 0) for u in usage.values()),
    }
    t["tokens"] = {k: sum(s[k] for s in t["sessions"].values()) for k in ("input", "cache_read", "output")}
    t["models"] = sorted({*t.get("models", []), *usage})  # what really ran, fallbacks included
    store.save(t)
    # shortcut: the budget is checked between steps, so one step can overshoot it; agent_minutes bounds that step
    used, budget = t["tokens"]["input"] + t["tokens"]["output"], CFG["limits"]["max_tokens"]
    if used > budget:
        raise RuntimeError(f"Token budget exceeded: {used:,} > {budget:,} (config.toml [limits] max_tokens)")
    return r


def sh(t: dict, cmd: str, cwd: Path, label: str | None = None, expect_fail: bool = False, **kw) -> tuple[bool, str]:
    """Run a command in the sandbox and stream it to the live feed. expect_fail: failing is the good outcome."""
    store.emit(t, "cmd", cmd=cmd, **({"label": label} if label else {}),
               **({"expect_fail": True} if expect_fail else {}))
    ok, out = sandbox.run(cmd, cwd, CFG["limits"]["command_seconds"],
                          lambda line: store.emit(t, "out", text=line), **kw)
    store.emit(t, "exit", ok=ok)
    return ok, f"$ {cmd}\n{out}"


def checks(t: dict, cmds: list[str], cwd: Path) -> tuple[bool, str]:
    """Run the project's check commands in order and stop at the first failure."""
    outs = []
    for cmd in cmds:
        ok, out = sh(t, cmd, cwd)
        outs.append(out)
        if not ok:
            return False, "\n".join(outs)
    return True, "\n".join(outs)


def findings(review: dict, severity: str | None = None) -> str:
    """Review findings as a list, optionally of one severity."""
    return "\n".join(f"- [{f['severity']}] {f['file']}: {f['message']}" for f in review["findings"]
                     if severity in (None, f["severity"]))


def project_error(t: dict) -> str | None:
    if t["project"] in CFG["projects"]:  # only names from config: a ticket's value is never used as a path
        return None
    return (f"Ticket has no valid project ({t['project'] or 'empty'}). "
            f"Add `project: <name>` to the ticket's front matter. Projects: {', '.join(CFG['projects'])}")


def bash_sandbox(wt: Path) -> dict:
    """Claude Code settings for the coding agent's Bash: no network; of the home folder only the worktree and Node."""
    root = sandbox.node_root()
    return {
        "env": {"PATH": f"{root}/bin:/usr/local/bin:/usr/bin:/bin"},  # its sandbox cannot read fnm/nvm shell setup
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,  # never fall back to running without the sandbox
            "allowUnsandboxedCommands": False,
            "autoAllowBashIfSandboxed": False,  # keep the allowed_bash list from config.toml in force
            "network": {"allowedDomains": []},
            "filesystem": {"denyRead": ["~/", *sandbox.host_mounts()], "allowRead": [str(wt.resolve()), str(root)]},
        },
    }


# --- steps -----------------------------------------------------------------------------------------------------

def triage(t: dict, ticket: str, wt: Path, guide: str) -> str | None:
    """Ask the triage agent. Returns the plan, or None when the ticket now waits for answers or is rejected."""
    tri = ask(t, prompt("triage", ticket=ticket), wt, READ_ONLY,
              schema=TRIAGE_SCHEMA, system=guide)["structured_output"]
    t["triage"] = tri
    if tri["decision"] == "question":
        if not tri["questions"]:
            raise RuntimeError("Triage chose to ask questions but returned none")
        t["questions"] = tri["questions"]
        store.move(t, "question", "The agent asked questions, waiting for an answer")
        return None
    if tri["decision"] == "reject":
        store.move(t, "rejected", "Ticket rejected, see the reason above")
        return None
    return tri["plan"]


def test_validity(t: dict, rc: dict, repo_path: Path, wt: Path, base_sha: str) -> str:
    """Run the new and changed tests against the code before the change: tests that verify the change fail there.

    The result is a note for the reviewer, not a gate: a refactor that keeps behavior passes on both.
    """
    if not rc.get("test_file") or not rc.get("test_run"):
        return "Test validity is not configured for this project."
    files = [f for f in repo.changed_files(repo_path, wt, base_sha) if re.search(rc["test_file"], f)]
    if not files:
        store.log(t, "Test validity: no test files were added or changed")
        return "No test files were added or changed."
    names = ", ".join(files)
    store.log(t, f"Test validity: running {names} against the unchanged base code")
    base = store.path(t["id"]) / "base"
    try:
        repo.base_copy(repo_path, base_sha, base, wt, files)
        ok, _ = sh(t, rc["setup"], base, "Base code", network=True, cache=settings.RUNS / ".npm-cache")
        if not ok:
            return "Test validity could not be measured: setup failed on the base code."
        passed, out = sh(t, f"{rc['test_run']} {' '.join(map(shlex.quote, files))}", base, "Base code",
                         expect_fail=True)
    finally:
        repo.remove_worktree(repo_path, base)
    if passed:
        store.log(t, "Warning: the new tests also pass on the base code, so they may not verify the change")
        return (f"{names} also PASS on the unchanged base code. "
                "These tests may not verify the behavior the ticket asks for.")
    tail = out[-1500:]
    # a run that never got to the tests says nothing about them
    if re.search(r"^timed out \(\d+s\)$|no test files found|no tests ran", out, re.I | re.M):
        store.log(t, "Test validity could not be measured: the tests did not run on the base code")
        return f"Test validity could not be measured: the tests did not run on the base code.\n\n{tail}"
    store.log(t, "Test validity: the new tests fail on the base code")
    return (f"{names} FAIL on the unchanged base code and pass with the change. Check in the output below that they "
            f"fail for the reason the ticket is about, not only because a new file is missing on the base code.\n\n"
            f"{tail}")


def implement(t: dict, ticket: str, plan: str, rc: dict, repo_path: Path, wt: Path, base_sha: str, guide: str) -> None:
    """Coding, checks and review, in rounds, until the review approves. Raises when the rounds run out."""
    check_cmds = ", ".join(f"`{c}`" for c in rc["check"])
    # Read/Edit/Write are not listed: the permission mode allows them only inside the worktree
    allowed = [f"Bash({c})" for c in rc["allowed_bash"]]
    allowed_text = ", ".join(f"`{c}`" for c in rc["allowed_bash"])
    session, feedback = None, ""
    for rnd in range(1, CFG["limits"]["rounds"] + 1):
        t["round"] = rnd
        store.move(t, "coding", f"Round {rnd}: coding")
        text = (prompt("code", ticket=ticket, plan=plan, check=check_cmds, allowed=allowed_text) if session is None
                else prompt("fix", feedback=feedback, check=check_cmds))
        r = ask(t, text, wt, CODE_TOOLS, allowed=allowed, mode="acceptEdits", resume=session,
                settings=bash_sandbox(wt), system=guide)
        session = r["session_id"]
        t["work"] = (r.get("result") or "").strip()  # the agent's closing summary becomes the commit message

        store.move(t, "checking", f"Round {rnd}: checks")
        ok, out = checks(t, rc["check"], wt)
        t["check"] = out[-TAIL:]
        t["diff"] = repo.diff(repo_path, wt, base_sha)
        if not ok:
            for k in ("tests", "review"):
                t.pop(k, None)  # they belong to an older round
            feedback = f"The check commands failed:\n\n{out[-TAIL:]}"
            store.log(t, "Checks failed, back to coding")
            continue
        if not t["diff"].strip():
            feedback = "You made no changes. Implement the ticket."
            store.log(t, "No changes, back to coding")
            continue

        t["tests"] = test_validity(t, rc, repo_path, wt, base_sha)

        store.move(t, "review", f"Round {rnd}: review")
        last = t.get("last_review")
        previous = f"{last['summary']}\n\n{findings(last)}".strip() if last else "None: this is the first review."
        rv = ask(t, prompt("review", ticket=ticket, plan=plan, diff=t["diff"], tests=t["tests"], previous=previous),
                 wt, READ_ONLY, schema=REVIEW_SCHEMA, system=guide)["structured_output"]
        t["review"] = t["last_review"] = rv
        blockers = findings(rv, "blocker")
        if rv["approved"] and not blockers:
            return
        minors = findings(rv, "minor")
        feedback = (f"The review found these problems:\n\n{blockers or rv['summary']}"
                    + (f"\n\nMinor points, fix them only if it is easy:\n\n{minors}" if minors else "")
                    + f"\n\nTest validity: {t['tests']}")
        store.log(t, "Review not approved, back to coding")
    raise RuntimeError(f"Checks and review did not pass within {CFG['limits']['rounds']} rounds")


def publish(t: dict, rc: dict, repo_path: Path) -> None:
    """Push the branch and open a merge request when GitLab is on, then mark the ticket done."""
    gl = CFG.get("gitlab", {})
    if gl.get("enabled") and rc.get("gitlab_project"):
        store.move(t, "delivering", "Delivery: pushing the branch and opening a merge request")
        t["mr"] = gitlab.deliver(gl, rc["gitlab_project"], repo_path, t["branch"], t["base"],
                                 f"{t['id']}: {t['title']}", mr_text(t))
    store.move(t, "done", f"Ready: {t.get('mr') or 'branch ' + t['branch']}")


def mr_text(t: dict) -> str:
    return "\n\n".join(part for part in (
        f"Ticket: {t['jira']}" if t.get("jira") else "",  # GitLab links Jira keys when its integration is on
        "## Changes\n\n" + (t.get("work") or t["triage"]["plan"]),
        "## Review\n\n" + (t.get("review") or {}).get("summary", ""),
        "## Tests\n\n" + t.get("tests", "").split("\n\n")[0],  # the note without the test output
        "Opened by handoff. A person reviews and merges it.",
    ) if part)


# --- one ticket ------------------------------------------------------------------------------------------------

def run_ticket(t: dict, stop: threading.Event) -> None:
    """Run one ticket. Any error fails this ticket only; the worker goes on with the next one."""
    try:
        _run(t)
    except agent.Refused as e:  # a refusal is a rejection: a retry would be refused again
        t["error"] = str(e)
        store.move(t, "rejected", "The model refused to work on this ticket")
    except Exception as e:
        if stop.is_set():
            return  # the server is stopping: keep the stage, so the ticket is queued again on start
        traceback.print_exc()
        t["error"] = str(e) or type(e).__name__
        t["failed_stage"] = t["stage"]
        store.move(t, "failed", f"Failed: {t['error'].splitlines()[0]}")  # the full text is in t["error"]
    finally:
        if t["stage"] in ("question", "rejected", "failed"):
            clean_up(t)


def clean_up(t: dict) -> None:
    """Remove the worktree and the empty branch of a ticket that stopped before delivery.

    Its diff and command output stay in state.json. A ticket with a worktree has delivered nothing yet.
    """
    wt = store.path(t["id"]) / "wt"
    if wt.exists():
        repo_path = settings.PROJECTS / t["project"]
        repo.remove_worktree(repo_path, wt)
        repo.drop_branch(repo_path, t["id"], t["base"])


def _run(t: dict) -> None:
    ticket = store.text(t)
    t["project"] = store.front_matter(ticket).get("project", "")  # read again: it may have been fixed before Retry
    if err := project_error(t):
        raise RuntimeError(err)
    rc = CFG["projects"][t["project"]]
    repo_path = settings.PROJECTS / t["project"]
    if t.get("branch"):
        # the commit is on the branch already: only the push or the merge request failed, or the server stopped
        # during them. Retry just those (a full run would stop at the unmerged branch).
        t.pop("error", None)
        t.pop("failed_stage", None)
        return publish(t, rc, repo_path)

    for k in ATTEMPT_KEYS:
        t.pop(k, None)
    t["round"] = 0
    t["base"] = rc["base_branch"]
    # agents load no project files (agent.py), so CLAUDE.md comes from the base branch
    guide = repo.git(repo_path, "show", f"{rc['base_branch']}:CLAUDE.md", check=False).stdout
    guide = f"Project instructions (CLAUDE.md):\n\n{guide}" if guide.strip() else ""
    # agents see the ticket without its front matter: `project` is pipeline config, `expect` is for scripts/eval.py
    ticket = re.sub(r"\A---\n.*?\n---[ \t]*\n", "", ticket, flags=re.S).strip()

    store.move(t, "triage", "Triage started")
    # triage reads the base branch in the ticket's worktree, not the checkout, which a person may have switched
    wt = store.path(t["id"]) / "wt"
    base_sha = repo.worktree(repo_path, rc["base_branch"], t["id"], wt)
    plan = triage(t, ticket, wt, guide)
    if plan is None:
        return  # run_ticket removes the worktree

    store.move(t, "coding", "Preparing the worktree")
    ok, out = sh(t, rc["setup"], wt, network=True, cache=settings.RUNS / ".npm-cache")  # setup needs the network
    if not ok:
        raise RuntimeError(f"Setup failed:\n{out[-TAIL:]}")

    implement(t, ticket, plan, rc, repo_path, wt, base_sha, guide)

    store.move(t, "delivering", "Delivery: committing")
    repo.deliver(repo_path, wt, f"{t['id']}: {t['title']}\n\n{t['work'] or plan}")
    t["branch"] = repo.branch(t["id"])
    publish(t, rc, repo_path)


# --- background threads ----------------------------------------------------------------------------------------

def intake_loop(stop: threading.Event) -> None:
    """Watch the inbox. Runs apart from the worker, so a ticket dropped during a long run shows up at once."""
    while not stop.is_set():
        try:
            store.ingest_inbox(project_error)
        except Exception:
            traceback.print_exc()
        stop.wait(CFG["limits"]["poll_seconds"])


def worker_loop(stop: threading.Event) -> None:
    """Run queued tickets one at a time, oldest first."""
    try:
        store.requeue_interrupted()
    except Exception:
        traceback.print_exc()
    while not stop.is_set():
        try:
            t = next((t for t in store.all_tickets() if t["stage"] == "queued"), None)
        except Exception:
            traceback.print_exc()
            t = None
        if not t:
            stop.wait(CFG["limits"]["poll_seconds"])
            continue
        try:
            run_ticket(t, stop)
        except Exception:  # the failure handling itself broke (a full disk, say): keep the queue moving
            traceback.print_exc()
