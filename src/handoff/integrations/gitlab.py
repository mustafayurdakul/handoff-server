"""GitLab delivery (config.toml [gitlab], off by default): push the ticket branch and open a merge request.

The token comes from the GITLAB_TOKEN environment variable, never from config.toml. Only the server uses
it: agents and sandboxed commands get an environment without it.
"""
import base64
import os
import subprocess
from pathlib import Path
from urllib.parse import quote

from . import rest


def push(repo: Path, branch: str, remote: str, token: str) -> None:
    # the token reaches git through the environment, so it is not visible in the process list
    header = "Authorization: Basic " + base64.b64encode(f"oauth2:{token}".encode()).decode()
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0",
           "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.extraHeader", "GIT_CONFIG_VALUE_0": header}
    p = subprocess.run(["git", "-C", str(repo), "push", remote, f"{branch}:refs/heads/{branch}"],
                       capture_output=True, text=True, env=env)
    if p.returncode:
        raise RuntimeError(f"git push to GitLab failed:\n{p.stderr.strip()}")


def open_mr(url: str, token: str, project: str, branch: str, target: str, title: str, description: str) -> str:
    """Open a merge request and return its web URL."""
    mr = rest.request("POST", f"{url}/api/v4/projects/{quote(project, safe='')}/merge_requests",
                      {"PRIVATE-TOKEN": token},
                      {"source_branch": branch, "target_branch": target, "title": title,
                       "description": description, "remove_source_branch": True})
    return mr["web_url"]


def deliver(cfg: dict, project: str, repo: Path, branch: str, target: str, title: str, description: str) -> str:
    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        raise RuntimeError("GitLab is enabled in config.toml, but GITLAB_TOKEN is not set")
    url = cfg["url"].rstrip("/")
    push(repo, branch, f"{url}/{project}.git", token)
    return open_mr(url, token, project, branch, target, title, description)
