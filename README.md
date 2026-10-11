# handoff-server

handoff takes a ticket, lets Claude Code agents write and review the code, and leaves a branch for a person to merge.

The web UI is a separate repository: `handoff-ui`.

## Setup

```sh
sudo apt install python3-venv bubblewrap socat
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env
sh demo/setup.sh                       # the demo repository; its scenes: demo/README.md
```

## Run

```sh
.venv/bin/handoff                      # API on http://127.0.0.1:8765
```

Then start `handoff-ui` (`npm run dev`, UI on http://127.0.0.1:5173).

To add a ticket, put a `.md` file into the inbox folder (`HANDOFF_INBOX` in `.env`, default `inbox/`).
