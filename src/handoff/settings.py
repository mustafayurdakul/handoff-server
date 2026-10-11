"""Settings. Folders and the address come from the environment (or a .env file); the rest from config.toml."""
import os
import tomllib
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Read KEY=value lines into the environment. Variables that are already set win."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser().resolve()


_load_dotenv(Path(".env"))

INBOX = _path("HANDOFF_INBOX", "inbox")  # new tickets: .md files dropped here
RUNS = _path("HANDOFF_RUNS", "runs")  # one folder per ticket: state, live feed, working copy
PROJECTS = _path("HANDOFF_PROJECTS", "projects")  # the git repositories named in config.toml
HOST = os.environ.get("HANDOFF_HOST", "127.0.0.1")  # the API has no login: keep it on this machine
PORT = int(os.environ.get("HANDOFF_PORT", "8765"))
CONFIG = tomllib.loads(_path("HANDOFF_CONFIG", "config.toml").read_text())
PROMPTS = Path(__file__).parent / "prompts"
