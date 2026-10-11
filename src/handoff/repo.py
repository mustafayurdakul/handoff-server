"""Git on the target repositories: a worktree and a branch per ticket, the diff, and the delivery commit."""
import shutil
import subprocess
from pathlib import Path

BOT = ["-c", "user.name=handoff", "-c", "user.email=handoff@localhost"]


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, encoding="utf-8", errors="replace")
    if check and p.returncode:
        # name the subcommand and keep git's own message: that is the useful part
        cmd = next((a for a in args if not a.startswith("-") and "=" not in a), "")
        raise RuntimeError(f"git {cmd} failed: {p.stderr.strip() or p.stdout.strip()}")
    return p


def branch(tid: str) -> str:
    return f"handoff/{tid}"


def remove_worktree(repo: Path, path: Path) -> None:
    git(repo, "worktree", "remove", "--force", str(path), check=False)
    shutil.rmtree(path, ignore_errors=True)
    git(repo, "worktree", "prune")


def drop_branch(repo: Path, tid: str, base: str) -> None:
    """Delete the ticket branch of an earlier attempt. A delivered branch with work not on base must survive."""
    if not git(repo, "branch", "--list", branch(tid)).stdout:
        return
    # against base, not HEAD (what `branch -d` uses): a person may have checked out anything in the repository
    if git(repo, "merge-base", "--is-ancestor", branch(tid), base, check=False).returncode:
        raise RuntimeError(f"Branch {branch(tid)} has unmerged work from an earlier delivery. "
                           "Merge or delete it first.")
    git(repo, "branch", "-D", branch(tid))


def worktree(repo: Path, base: str, tid: str, wt: Path) -> str:
    """Open a clean worktree on a new ticket branch. Returns the base commit."""
    remove_worktree(repo, wt)  # left over from an earlier attempt
    drop_branch(repo, tid, base)
    sha = git(repo, "rev-parse", base).stdout.strip()
    git(repo, "worktree", "add", "-b", branch(tid), str(wt), sha)
    return sha


def wt_git(repo: Path, wt: Path, *args: str) -> subprocess.CompletedProcess:
    """git on a ticket worktree that trusts nothing inside it.

    Sandboxed code can rewrite anything in the worktree, its .git file included, and plain `git -C wt` would
    follow that file to a config that runs commands on the host. So the gitdir comes from the main repository,
    and hooks are off because a hooks folder inside the worktree (husky) is writable too.
    """
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip())
    target = f"{wt.resolve()}/.git"
    gitdir = next((d for d in (common / "worktrees").iterdir()
                   if (d / "gitdir").is_file() and (d / "gitdir").read_text().strip() == target), None)
    if gitdir is None:
        raise RuntimeError(f"{wt} is not a worktree of {repo}")
    return git(wt, f"--git-dir={gitdir}", f"--work-tree={wt}", "-c", "core.hooksPath=/dev/null",
               "-c", "core.quotePath=false", *args)  # quotePath: the UI expects plain file names


def diff(repo: Path, wt: Path, base_sha: str) -> str:
    wt_git(repo, wt, "add", "-A")
    # against the base commit, so the changes show even if the agent committed despite the rules
    return wt_git(repo, wt, "diff", "--cached", base_sha).stdout


def changed_files(repo: Path, wt: Path, base_sha: str) -> list[str]:
    """Files added or modified since the base commit (deletions left out)."""
    wt_git(repo, wt, "add", "-A")
    out = wt_git(repo, wt, "diff", "--cached", "--name-only", "-z", "--no-renames", "--diff-filter=AM", base_sha).stdout
    return [f for f in out.split("\0") if f]


def base_copy(repo: Path, base_sha: str, path: Path, wt: Path, files: list[str]) -> None:
    """Open a detached worktree at the base commit and copy the given files from the ticket worktree into it."""
    remove_worktree(repo, path)
    git(repo, "worktree", "add", "--detach", str(path), base_sha)
    for f in files:
        (path / f).parent.mkdir(parents=True, exist_ok=True)
        # a symlink is copied as a link, so a link to a host file does not pull that file in
        shutil.copy2(wt / f, path / f, follow_symlinks=False)


def deliver(repo: Path, wt: Path, message: str) -> None:
    """Commit everything on the ticket branch and remove the worktree. The branch stays."""
    wt_git(repo, wt, "add", "-A")
    wt_git(repo, wt, *BOT, "commit", "-m", message)
    remove_worktree(repo, wt)  # never fails: a delivered ticket must not fail on cleanup
