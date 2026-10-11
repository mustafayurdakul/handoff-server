# handoff

Takes a ticket through Claude Code agents to a reviewed branch, and hands it back to a person to merge.

```
ticket (.md in the inbox, or a Jira issue)
  → Triage → Coding → Checks → Review → Delivery: branch handoff/<id> (+ GitLab merge request)
     │         ↑________│_________│      at most 3 rounds
     ├─ Question → answered in the UI or in Jira → back to the queue
     └─ Rejected
```

Every step is a `claude -p` run on the machine's Claude Code login, so no API key is needed. The pipeline runs the
check commands (lint, test, build) itself, in a sandbox. It also runs the new tests against the code before the
change: tests that verify the change must fail there, and the reviewer sees the result. A person always merges.

The web UI is a separate repository, [handoff-ui](../handoff-ui). This repository is the pipeline and its API.

## Setup

```sh
sudo apt install python3-venv bubblewrap socat
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env          # folders and address; the defaults work as they are
sh demo/setup.sh              # creates the demo repositories in HANDOFF_PROJECTS
.venv/bin/pytest              # sandbox, git safety, pipeline logic, integrations
```

On Ubuntu 24.04 and later, the coding agent's own Bash sandbox needs an AppArmor change. Without it the agent
cannot run commands itself; the pipeline still runs the checks. Add the profile from the Claude Code docs
([sandboxing](https://code.claude.com/docs/en/sandboxing)):

```sh
sudo tee /etc/apparmor.d/bwrap > /dev/null <<'EOF'
abi <abi/4.0>,
include <tunables/global>

profile bwrap /usr/bin/bwrap flags=(unconfined) {
  userns,
  include if exists <local/bwrap>
}
EOF
sudo systemctl reload apparmor
```

If Ubuntu's own `bwrap-userns-restrict` profile is loaded too, it still wins (`apply-seccomp: ... Permission
denied`). Turn it off for bwrap only; to undo, remove the link and run
`sudo apparmor_parser -r /etc/apparmor.d/bwrap-userns-restrict`:

```sh
sudo ln -s /etc/apparmor.d/bwrap-userns-restrict /etc/apparmor.d/disable/
sudo apparmor_parser -R /etc/apparmor.d/bwrap-userns-restrict
```

## Running

```sh
.venv/bin/handoff                         # API on http://127.0.0.1:8765, then start handoff-ui
cp demo/tickets/APP-1.md inbox/           # drop a ticket into HANDOFF_INBOX
.venv/bin/python scripts/eval.py APP-2    # run demo tickets and compare with their expected outcome
```

Stopping with Ctrl+C is safe: a ticket that was running is queued again on the next start.

## Configuration

Folders and the address come from the environment, or from a `.env` file in the folder handoff starts from
(see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `HANDOFF_INBOX` | `./inbox` | Folder watched for new tickets (`.md` files) |
| `HANDOFF_RUNS` | `./runs` | Ticket state, live feeds and working copies |
| `HANDOFF_PROJECTS` | `./projects` | The git repositories the agents work on |
| `HANDOFF_CONFIG` | `./config.toml` | The file below |
| `HANDOFF_HOST`, `HANDOFF_PORT` | `127.0.0.1`, `8765` | API address. It has no login: keep it local. |
| `JIRA_TOKEN`, `GITLAB_TOKEN` | | Only when Jira or GitLab is enabled |

`config.toml` holds everything else:

- `[projects.<name>]`: one per repository in `HANDOFF_PROJECTS`. Base branch, setup and check commands, the
  commands the agent may run, and the test file pattern for the test validity check. The `CLAUDE.md` at the root
  of the base branch is given to every agent.
- `[agent]`: model and effort for every step. `[limits]`: rounds, time limits, and the token budget per ticket.
- `[jira]`, `[gitlab]`: off by default, see below.

## Tickets

A ticket is a markdown file. The front matter names the project; the rest is free text:

```markdown
---
project: demo-app
---

# Add date sorting to the document list

## Description

What is needed, and why?

## Acceptance criteria

- A testable statement that must be true when the work is done
```

`demo/tickets/` has ten examples for the three demo projects (React app, Fastify API, Python library): clear
features, two real bugs planted in the demos, vague and too large requests, and a ticket with injected
instructions that the agents must ignore. Each states its expected outcome in `expect:`, which `scripts/eval.py`
checks. Agents never see the front matter.

## Jira and GitLab

Both are off in `config.toml`. To turn them on, fill in `[jira]` (site, bot account email, JQL, Jira project key
→ handoff project) and `[gitlab]` (URL), set `gitlab_project` in each project, set `enabled = true`, and start
handoff with `JIRA_TOKEN` and `GITLAB_TOKEN` in its environment.

- Issues that match the JQL become tickets, keyed by the issue key. Description and comments are the ticket text.
- The outcome goes back as a comment and a label: `handoff-question`, `handoff-rejected`, `handoff-failed` or
  `handoff-done` (with the merge request link).
- To answer or try again, a person comments on the issue and removes the label. The next poll queues it again.

## Layout

```
src/handoff/
  __main__.py        starts the API server
  settings.py        environment and config.toml
  api.py             HTTP API and live feed (SSE) for the UI; starts the pipeline threads
  pipeline.py        the steps: triage, coding rounds, checks, test validity, review, delivery
  agent.py           one `claude -p` run, streamed
  sandbox.py         bubblewrap sandbox and child process control
  repo.py            git worktrees, safe git on worktrees, the delivery commit
  store.py           ticket state on disk and inbox intake
  prompts/           the four agent prompts
  integrations/      jira.py, gitlab.py, rest.py
tests/               pytest
scripts/eval.py      runs the demo tickets against a running server
demo/                demo projects, setup.sh, demo tickets
```

## Security

Ticket text is untrusted, and the code the agent writes runs during tests and builds.

- Setup and checks run in bubblewrap: read-only system, hidden home folder and `/run/user`, writes only to the
  worktree, a clean environment, and no network (setup gets the network for the package registry).
- The coding agent's Bash runs in Claude Code's sandbox: no network, and of the home folder only the worktree and
  Node are readable. Its file tools are kept inside the worktree by Claude Code permissions.
- If a sandbox cannot start, nothing runs without it: the server does not start, and agent calls fail.
- Agents load only the user's Claude Code settings and the pipeline's flags, never `.claude/` from a worktree.
- git on a worktree takes its gitdir from the main repository and runs with hooks off, since sandboxed code can
  rewrite both.
- Jira and GitLab tokens live only in the server's environment. A person always merges.
