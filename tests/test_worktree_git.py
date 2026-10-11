"""git on ticket worktrees: it ignores what sandboxed code plants there, and never deletes a delivered branch."""
import shutil
import subprocess

import pytest

from handoff import repo, sandbox

pytestmark = pytest.mark.skipif(shutil.which("bwrap") is None, reason="bubblewrap is not installed")

# what check code could do inside the sandbox: swap .git for a repository whose config runs a script
# (core.fsmonitor), and fill the hooks folder the project keeps inside the worktree (as husky does)
PLANT = """
printf '#!/bin/sh\\ntouch {marker}\\n' > h.sh && chmod +x h.sh
mkdir -p .hooks && cp h.sh .hooks/pre-commit
rm .git && git init -q . && git config core.fsmonitor "$PWD/h.sh"
"""


@pytest.fixture
def main_repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    repo.git(r, "init", "-q", "-b", "main")
    repo.git(r, "config", "core.hooksPath", ".hooks")
    (r / "a.txt").write_text("a\n")
    repo.git(r, "add", "-A")
    repo.git(r, *repo.BOT, "commit", "-qm", "base")
    return r


def test_planted_git_config_and_hooks_never_run(main_repo, tmp_path):
    wt, marker = tmp_path / "wt", tmp_path / "escaped"
    sha = repo.worktree(main_repo, "main", "T-1", wt)
    p = subprocess.run(sandbox.command(PLANT.format(marker=marker), wt, network=False),
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    (wt / "b.txt").write_text("b\n")

    assert "b.txt" in repo.diff(main_repo, wt, sha)
    assert "b.txt" in repo.changed_files(main_repo, wt, sha)
    assert not marker.exists(), "diff ran a script planted in the worktree"

    # the trap itself works: plain git in the worktree follows the planted .git and runs the script
    subprocess.run(["git", "-C", str(wt), "status"], capture_output=True)
    assert marker.exists(), "the planted trap did not fire, so this test proves nothing"
    marker.unlink()

    repo.deliver(main_repo, wt, "T-1: test")
    assert not marker.exists(), "commit ran a hook planted in the worktree"
    files = repo.git(main_repo, "show", "--name-only", "--format=", repo.branch("T-1")).stdout.split()
    assert "b.txt" in files


def test_a_delivered_branch_survives_a_new_run(main_repo, tmp_path):
    wt = tmp_path / "wt"
    repo.worktree(main_repo, "main", "T-1", wt)
    (wt / "b.txt").write_text("b\n")
    repo.deliver(main_repo, wt, "T-1: test")
    # the same id again (runs folder cleared, ticket dropped again) must not delete the unmerged branch
    with pytest.raises(RuntimeError, match="unmerged work"):
        repo.worktree(main_repo, "main", "T-1", tmp_path / "wt2")
    assert repo.git(main_repo, "branch", "--list", repo.branch("T-1")).stdout


def test_a_failed_attempt_branch_is_replaced(main_repo, tmp_path):
    # a retry replaces the branch of a failed attempt, which has no commits of its own
    repo.worktree(main_repo, "main", "T-2", tmp_path / "wt")
    repo.worktree(main_repo, "main", "T-2", tmp_path / "wt")


def test_a_failed_attempt_branch_is_replaced_whatever_is_checked_out(main_repo, tmp_path):
    # a person checked out an older branch in the main repository, and main moved on since
    repo.git(main_repo, "branch", "old")
    (main_repo / "c.txt").write_text("c\n")
    repo.git(main_repo, "add", "-A")
    repo.git(main_repo, *repo.BOT, "commit", "-qm", "c")
    repo.git(main_repo, "checkout", "-q", "old")
    repo.worktree(main_repo, "main", "T-3", tmp_path / "wt")
    repo.worktree(main_repo, "main", "T-3", tmp_path / "wt")
