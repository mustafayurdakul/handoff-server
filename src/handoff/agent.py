"""One agent step: a headless `claude -p` run.

It uses the machine's Claude Code login, so no API key is needed. Agent notes, tool calls and tool
results go to on_event as they stream in.
"""
import json
import subprocess
import threading
from collections import deque
from pathlib import Path

from . import sandbox

# the user's own hooks (output styles and the like) stay out of pipeline agents
SETTINGS = {"disableAllHooks": True}
MAX_FIELD = 30_000  # Edit/Write content sent to the UI
MAX_OUTPUT = 8_000  # tool output sent to the UI (the tail is kept)


class AgentError(Exception):
    pass


class Refused(AgentError):
    """The model declined the request under its usage policy; trying again will not help."""


def _relative(value, prefix: str):
    """Strip the worktree prefix so the UI shows short relative paths."""
    if isinstance(value, str):
        return value.replace(prefix, "")
    if isinstance(value, dict):
        return {k: _relative(v, prefix) for k, v in value.items()}
    return value


def _tool_input(name: str, i: dict) -> dict:
    keep = {
        "Edit": ("file_path", "old_string", "new_string"),
        "Write": ("file_path", "content"),
        "Bash": ("command", "description"),
        "Read": ("file_path",),
        "Glob": ("pattern", "path"),
        "Grep": ("pattern", "path", "glob"),
    }.get(name)
    picked = {k: i[k] for k in keep if k in i} if keep else i
    return {k: v[:MAX_FIELD] if isinstance(v, str) else v for k, v in picked.items()}


def _output(content) -> str:
    if isinstance(content, list):
        content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return str(content or "")


def run(prompt, cwd: Path, tools, *, model, effort, timeout, allowed=(), mode="dontAsk", schema=None, resume=None,
        settings=None, system="", on_event=lambda e: None) -> dict:
    cmd = [
        "claude", "-p", "--output-format", "stream-json", "--verbose",
        "--model", model, "--effort", effort,
        "--tools", ",".join(tools), "--permission-mode", mode,
        "--settings", json.dumps({**SETTINGS, **(settings or {})}), "--strict-mcp-config",
        # no project or local settings: code run by the checks can write .claude/ in the worktree
        "--setting-sources", "user",
    ]
    if system:
        cmd += ["--append-system-prompt", system]
    if allowed:
        cmd += ["--allowedTools", *allowed]
    if schema:
        cmd += ["--json-schema", json.dumps(schema)]
    if resume:
        cmd += ["--resume", resume]

    # prompt goes in on stdin: prompts that carry a diff can exceed the 128 KB single-argument limit
    proc = sandbox.spawn(cmd, cwd=cwd, encoding="utf-8", errors="replace", stdin=subprocess.PIPE,
                         env=sandbox.agent_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    timer = threading.Timer(timeout, sandbox.kill, [proc])
    timer.start()
    try:
        return _read(proc, prompt, cwd, timeout, schema, on_event)
    finally:
        timer.cancel()
        if proc.poll() is None:  # an error while reading: do not leave claude running
            sandbox.kill(proc)
            proc.wait()
        sandbox.done(proc)


def _read(proc, prompt, cwd, timeout, schema, on_event) -> dict:
    proc.stdin.write(prompt)
    proc.stdin.close()

    prefix = f"{Path(cwd).resolve()}/"
    names: dict[str, str] = {}  # tool_use_id -> tool name
    result, tail = None, deque(maxlen=20)
    for line in proc.stdout:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            tail.append(line.rstrip())
            continue
        kind = msg.get("type")
        if kind == "assistant":
            for b in msg["message"]["content"]:
                if b.get("type") in ("text", "thinking") and (b.get("text") or b.get("thinking", "")).strip():
                    on_event({"kind": "text", "text": b.get("text") or b["thinking"]})
                elif b.get("type") == "tool_use" and b["name"] != "StructuredOutput":
                    names[b["id"]] = b["name"]
                    on_event({"kind": "tool", "id": b["id"], "name": b["name"],
                              "input": _relative(_tool_input(b["name"], b.get("input") or {}), prefix)})
        elif kind == "user":
            for b in msg["message"].get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in names:
                    out = _output(b.get("content"))
                    if names[b["tool_use_id"]] == "Read" and not b.get("is_error"):
                        out = f"{out.count(chr(10)) + 1} lines read"
                    on_event({"kind": "result", "id": b["tool_use_id"], "is_error": bool(b.get("is_error")),
                              "output": _relative(out[-MAX_OUTPUT:], prefix)})
        elif kind == "result":
            result = msg
    proc.wait()

    if result is None:
        raise AgentError(f"claude exited without a result (exit {proc.returncode}, {timeout}s limit): "
                         + "\n".join(tail))
    if result.get("is_error"):
        msg = str(result.get("result") or result.get("subtype"))
        # shortcut: recognized by the error text, since Claude Code has no separate field for it
        if "safeguards flagged" in msg or "/legal/aup" in msg:
            raise Refused(f"The model refused this ticket under its usage policy:\n\n{msg}")
        raise AgentError(f"claude returned an error: {msg}")
    if schema and not isinstance(result.get("structured_output"), dict):
        raise AgentError("claude returned no structured output")
    return result
