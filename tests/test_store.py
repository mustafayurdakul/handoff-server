"""Ticket files: front matter, and intake from the inbox folder."""
import os
import time

from handoff import settings, store


def test_front_matter():
    assert store.front_matter("---\nproject: demo-app   # comment\n---\n# T") == {"project": "demo-app"}
    assert store.front_matter("---\nproject: demo-app\n---\n# T") == {"project": "demo-app"}
    assert store.front_matter("# Title\nproject: x") == {}, "front matter only exists at the top"
    assert store.front_matter("---\nproject: demo-app\n# unclosed") == {}, "an unclosed block does not count"
    assert store.front_matter("") == {}


def test_inbox_files_become_tickets(runs, tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    monkeypatch.setattr(settings, "INBOX", inbox)
    ticket = inbox / "T-1.md"
    ticket.write_text("﻿---\nproject: demo-app\n---\n\n# Sort the list\n")  # with a BOM, as some editors save
    (inbox / "draft.md").write_text("")  # an editor's new, empty file
    old = time.time() - 10
    for f in inbox.iterdir():
        os.utime(f, (old, old))

    store.ingest_inbox(lambda t: None)

    t = store.load("T-1")
    assert (t["project"], t["title"], t["stage"]) == ("demo-app", "Sort the list", "queued")
    assert not ticket.exists(), "the file is moved out of the inbox"
    assert (inbox / "draft.md").exists(), "an empty file is left alone"
