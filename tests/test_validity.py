"""Test validity: a new test that fails on the old code verifies the change; one that passes there does not.

Uses the demo-app project in HANDOFF_PROJECTS (create it with demo/setup.sh) and runs npm ci in a worktree.
"""
import shutil

import pytest

from handoff import pipeline, repo, settings, store

DEMO = settings.PROJECTS / "demo-app"
pytestmark = [
    pytest.mark.skipif(shutil.which("bwrap") is None, reason="bubblewrap is not installed"),
    pytest.mark.skipif(not DEMO.exists(), reason="run demo/setup.sh first"),
]

GOOD = """import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import App from './App'

it('has a sort control', () => {
  render(<App />)
  expect(screen.getByRole('combobox', { name: 'Sort' })).toBeInTheDocument()
})
"""
USELESS = GOOD.replace("screen.getByRole('combobox', { name: 'Sort' })", "screen.getByRole('list')")


@pytest.mark.parametrize(("body", "expected"), [(GOOD, "FAIL on the unchanged base"), (USELESS, "also PASS")])
def test_validity(body, expected, tmp_path, monkeypatch):
    monkeypatch.setattr(store, "path", lambda tid: tmp_path)  # the base worktree goes to tmp_path/base
    monkeypatch.setattr(store, "emit", lambda *a, **kw: None)
    rc = settings.CONFIG["projects"]["demo-app"]
    sha = repo.git(DEMO, "rev-parse", rc["base_branch"]).stdout.strip()
    wt = tmp_path / "wt"
    repo.git(DEMO, "worktree", "add", "--detach", str(wt), sha)
    try:
        (wt / "src" / "New.test.tsx").write_text(body)
        assert expected in pipeline.test_validity({"id": "T"}, rc, DEMO, wt, sha)
    finally:
        repo.remove_worktree(DEMO, wt)
        repo.remove_worktree(DEMO, tmp_path / "base")
