"""Token accounting: a session continued with --resume reports a running total, which must not be counted twice."""
from pathlib import Path

import pytest

from handoff import agent, pipeline, store


def usage(inp: int, cached: int, out: int) -> dict:
    return {"claude-sonnet-5-5": {"inputTokens": inp, "cacheReadInputTokens": cached,
                                  "cacheCreationInputTokens": 0, "outputTokens": out}}


@pytest.fixture(autouse=True)
def no_disk(monkeypatch):
    monkeypatch.setattr(store, "save", lambda t: None)


def test_resumed_sessions_count_once(monkeypatch):
    # three coding rounds in one session, each reporting its running total, with a review session in between
    results = iter([
        {"session_id": "code", "modelUsage": usage(100, 1000, 10)},
        {"session_id": "review", "modelUsage": usage(50, 500, 5)},
        {"session_id": "code", "modelUsage": usage(200, 3000, 20)},
        {"session_id": "code", "modelUsage": usage(300, 6000, 30)},
    ])
    monkeypatch.setattr(agent, "run", lambda *a, **kw: next(results))
    t = {"id": "T"}
    for _ in range(4):
        pipeline.ask(t, "", Path("."), [])
    assert t["tokens"] == {"input": 300 + 6000 + 50 + 500, "cache_read": 6000 + 500, "output": 30 + 5}
    assert t["models"] == ["claude-sonnet-5-5"]


def test_budget_stops_the_ticket(monkeypatch):
    monkeypatch.setitem(pipeline.CFG["limits"], "max_tokens", 6_000)
    monkeypatch.setattr(agent, "run", lambda *a, **kw: {"session_id": "code", "modelUsage": usage(300, 6000, 30)})
    with pytest.raises(RuntimeError, match="Token budget exceeded"):
        pipeline.ask({"id": "T"}, "", Path("."), [])
