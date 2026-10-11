"""Runs the demo tickets through a running handoff server and compares each outcome with the ticket's `expect:`.

Usage, with the server running:  python scripts/eval.py [APP-1 PY-3 ...]   (no names: all demo tickets)
Every ticket makes real agent calls, so this costs tokens. Tickets run one at a time, like any queue.
"""
import re
import shutil
import sys
import time
from pathlib import Path

from handoff import settings, store

TICKETS = Path(__file__).resolve().parent.parent / "demo" / "tickets"
FINAL = ("done", "question", "rejected", "failed")


def new_id(stem: str, before: set[str]) -> str:
    """The id intake gives a copied file: its name, or name-2, name-3... when that id is taken."""
    same = re.compile(rf"^{re.escape(stem)}(-\d+)?$")
    while True:
        ids = [p.parent.name for p in settings.RUNS.glob("*/state.json") if same.match(p.parent.name)]
        if fresh := [i for i in ids if i not in before]:
            return fresh[0]
        time.sleep(1)


def main(names: list[str]) -> int:
    files = [TICKETS / f"{n}.md" for n in names] if names else sorted(TICKETS.glob("*.md"))
    runs = []
    for f in files:
        before = {p.parent.name for p in settings.RUNS.glob("*/state.json")}
        shutil.copy(f, settings.INBOX / f.name)
        runs.append((f, new_id(f.stem, before)))
        print(f"queued {f.stem} as {runs[-1][1]}", flush=True)

    failures = 0
    for f, tid in runs:
        expect = store.front_matter(f.read_text()).get("expect", "?")
        while (t := store.load(tid))["stage"] not in FINAL:
            time.sleep(5)
        ok = t["stage"] == expect
        failures += not ok
        tokens = t.get("tokens") or {}
        print(f"{'PASS' if ok else 'FAIL'}  {f.stem:<6} {tid:<9} expected {expect:<9} got {t['stage']:<9} "
              f"{tokens.get('input', 0) + tokens.get('output', 0):>9,} tokens", flush=True)
    print(f"{len(runs) - failures}/{len(runs)} as expected")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
