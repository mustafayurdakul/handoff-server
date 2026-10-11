"""Child processes and the command sandbox.

Every child runs in its own process group and is killed when the server stops. Commands that run
repository code (setup, lint, test, build) run in bubblewrap: read-only system, hidden home directory
and /run/user, writes only to the working directory, and a clean environment.
"""
import os
import re
import shutil
import signal
import subprocess
import threading
from collections import deque
from pathlib import Path

HOME = Path.home()
RUN_USER = Path(f"/run/user/{os.getuid()}")
# folders shared from the host machine: Windows drives on WSL (/mnt/c), the Mac home folder on Lima (/Users)
HOST_MOUNTS = ("/mnt", "/media", "/Users")
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# the only host variables a sandboxed command gets; none of them carries credentials
PASS_ENV = ("LANG", "LC_ALL", "TERM", "http_proxy", "https_proxy", "no_proxy", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")
# a test stuck in a print loop writes millions of lines: only this many reach the live feed, and the end is kept
MAX_LINES = 10_000
KEEP_LINES = 2_000
SECRET_ENV = re.compile(r"TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API_KEY|PRIVATE|^CLAUDE_CODE_|^CLAUDECODE$", re.I)

_running: set[subprocess.Popen] = set()
_lock = threading.Lock()
_stopping = threading.Event()  # set by kill_all: nothing new may start during shutdown


def node_root() -> Path:
    """The real root of the Node install, with fnm/nvm symlinks resolved."""
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node not found on PATH")
    return Path(node).resolve().parent.parent


def host_mounts() -> list[str]:
    """The HOST_MOUNTS that exist here: hidden from sandboxed code like the home folder."""
    return [d for d in HOST_MOUNTS if os.path.isdir(d)]


def agent_env() -> dict[str, str]:
    """Environment for `claude`: credential-like variables removed, ANTHROPIC_* kept (claude needs them)."""
    return {k: v for k, v in os.environ.items() if k.startswith("ANTHROPIC_") or not SECRET_ENV.search(k)}


def command(cmd: str, cwd: Path, *, network: bool, cache: Path | None = None) -> list[str]:
    """The bwrap command line that runs `cmd` in `cwd`."""
    root = node_root()
    argv = [
        "bwrap", "--die-with-parent", "--new-session", "--unshare-all",
        # no nested user namespaces: they give sandboxed code capabilities, a common way into kernel bugs
        "--unshare-user", "--disable-userns",
        "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
        "--tmpfs", str(HOME), "--tmpfs", str(RUN_USER), *(a for d in host_mounts() for a in ("--tmpfs", d)),
        "--ro-bind", str(root), str(root),
        "--bind", str(cwd), str(cwd),
        "--clearenv", "--setenv", "HOME", str(HOME), "--setenv", "CI", "1", "--setenv", "FORCE_COLOR", "1",
        "--setenv", "PATH", f"{root}/bin:/usr/local/bin:/usr/bin:/bin",
        "--chdir", str(cwd),
    ]
    if network:
        argv.append("--share-net")
    if cache:  # a shared npm download cache, so each setup does not download every package again
        cache.mkdir(parents=True, exist_ok=True)
        argv += ["--bind", str(cache), str(HOME / ".npm")]
    for k in PASS_ENV:
        if k in os.environ:
            argv += ["--setenv", k, os.environ[k]]
    return [*argv, "--", "/bin/sh", "-c", cmd]


def check() -> None:
    """Refuse to start when the sandbox does not work, rather than run commands without it."""
    hint = "Install: sudo apt install bubblewrap socat"
    try:
        p = subprocess.run(command('test ! -e "$HOME/.claude" && node --version', Path("/tmp"), network=False),
                           capture_output=True, text=True, timeout=30)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
        raise SystemExit(f"Sandbox is not working: {e}\n{hint}") from e
    if p.returncode != 0:
        raise SystemExit(f"Sandbox is not working:\n{p.stderr or p.stdout}\n{hint}")


def spawn(cmd: list[str], **kw) -> subprocess.Popen:
    with _lock:
        if _stopping.is_set():
            raise RuntimeError("The server is stopping")
        # its own process group: Ctrl+C reaches only the server, which then kills its children
        p = subprocess.Popen(cmd, start_new_session=True, **kw)
        _running.add(p)
    return p


def kill(p: subprocess.Popen) -> None:
    try:
        os.killpg(p.pid, signal.SIGKILL)  # the whole group, so grandchildren (npm -> vitest) die too
    except ProcessLookupError:
        pass


def done(p: subprocess.Popen) -> None:
    with _lock:
        _running.discard(p)


def kill_all() -> None:
    with _lock:
        _stopping.set()
        for p in list(_running):
            kill(p)


def run(cmd: str, cwd: Path, timeout: int, on_line, *, network: bool = False,
        cache: Path | None = None) -> tuple[bool, str]:
    """Run `cmd` in the sandbox and pass each output line to on_line, up to MAX_LINES.

    Returns (ok, the last KEEP_LINES lines of output without colors).
    """
    p = spawn(command(cmd, cwd, network=network, cache=cache), encoding="utf-8", errors="replace",
              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    timed_out = threading.Event()

    def stop() -> None:
        timed_out.set()
        kill(p)

    timer = threading.Timer(timeout, stop)
    timer.start()
    out = deque(maxlen=KEEP_LINES)
    try:
        for n, line in enumerate(p.stdout, 1):
            line = line.rstrip("\n")
            out.append(ANSI.sub("", line))
            if n <= MAX_LINES:
                on_line(line)
            elif n == MAX_LINES + 1:
                on_line(f"(output cut after {MAX_LINES:,} lines; the command goes on, and the end of it is kept)")
        p.wait()
    finally:
        timer.cancel()
        if p.poll() is None:  # an error while reading: do not leave the command running
            kill(p)
            p.wait()
        done(p)
    if timed_out.is_set():
        out.append(f"timed out ({timeout}s)")
        on_line(out[-1])
    return p.returncode == 0 and not timed_out.is_set(), "\n".join(out)
