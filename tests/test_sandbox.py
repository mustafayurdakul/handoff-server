"""The command sandbox: what code from a ticket can and cannot reach. Needs bubblewrap.

The coding agent's own Bash sandbox (Claude Code's) is not covered: testing it needs a claude call.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from handoff import sandbox

pytestmark = pytest.mark.skipif(shutil.which("bwrap") is None, reason="bubblewrap is not installed")
HOME = Path.home()


def sh(cmd: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(sandbox.command(cmd, cwd, network=False), capture_output=True, text=True, timeout=60)


def test_sandbox_starts():
    sandbox.check()


def test_node_runs_and_the_working_folder_is_writable(tmp_path):
    assert sh("node --version", tmp_path).returncode == 0
    assert sh("echo x > ok.txt", tmp_path).returncode == 0 and (tmp_path / "ok.txt").exists()


def test_home_and_run_user_are_hidden(tmp_path):
    secret = next(p for p in (HOME / ".claude", HOME / ".ssh", HOME / ".bashrc") if p.exists())
    assert sh(f"test -e {secret}", tmp_path).returncode != 0, f"{secret} is visible"
    assert sh(f"ls -A /run/user/{os.getuid()} | grep -q .", tmp_path).returncode != 0, "/run/user is visible"
    for d in sandbox.host_mounts():
        assert sh(f"ls -A {d} | grep -q .", tmp_path).returncode != 0, f"host folder {d} is visible"


def test_no_tokens_and_no_network(tmp_path, monkeypatch):
    monkeypatch.setenv("GITLAB_TOKEN", "secret-value")
    assert "secret-value" not in sh("env", tmp_path).stdout
    fetch = "node -e \"fetch('https://example.com').then(()=>process.exit(0),()=>process.exit(1))\""
    assert sh(fetch, tmp_path).returncode != 0, "the network is reachable"



def test_no_nested_user_namespaces(tmp_path):
    assert sh("unshare -U -r true", tmp_path).returncode != 0, "sandboxed code can create a user namespace"

def test_no_writes_outside(tmp_path):
    escape = HOME / "handoff-sandbox-escape"
    sh(f"echo x > {escape}", tmp_path)
    assert not escape.exists(), "wrote to the home folder"
    assert sh("touch /etc/handoff-sandbox-escape", tmp_path).returncode != 0, "wrote to the system"


def test_endless_output_is_cut(tmp_path):
    lines = []
    ok, out = sandbox.run(f"seq {sandbox.MAX_LINES * 3}", tmp_path, 60, lines.append)
    assert ok and len(lines) == sandbox.MAX_LINES + 1, "every line went to the live feed"
    assert len(out.splitlines()) == sandbox.KEEP_LINES and out.endswith(str(sandbox.MAX_LINES * 3)), "end not kept"
