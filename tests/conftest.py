import pytest

from handoff import settings


@pytest.fixture
def runs(tmp_path, monkeypatch):
    """Ticket state goes to a temporary folder instead of HANDOFF_RUNS."""
    monkeypatch.setattr(settings, "RUNS", tmp_path / "runs")
    return settings.RUNS
