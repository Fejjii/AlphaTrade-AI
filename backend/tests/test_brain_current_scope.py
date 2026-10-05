"""Current Agent setup reads preserve family, timeframe and episode scope."""

from uuid import uuid4

from app.strategy_brain.agent import read_brain


def test_current_nested_read_excludes_other_families_timeframes_and_old_episodes(monkeypatch):
    version = uuid4()

    def setup(**changes):
        return {
            "setup_id": str(uuid4()),
            "strategy_version_id": version,
            "family": "nested",
            "timeframe": "15m",
            "state": "FORMING",
            "stage": "N1",
            "direction": "long",
            "observed_at": "2026-10-05T12:30:00Z",
            "expires_at": "2026-10-05T13:30:00Z",
            "freshness": "AVAILABLE",
            "candidate_id": None,
            "journal": None,
            "decision_id": None,
            "evidence": {"order_flow": "UNSUPPORTED"},
            **changes,
        }

    current = setup()
    old = setup(state="EXPIRED")
    other_interval = setup(timeframe="4h", strategy_version_id=uuid4())
    other_family = setup(family="sfp", strategy_version_id=uuid4())
    monkeypatch.setattr(
        "app.strategy_brain.agent.overview",
        lambda *a, **k: {
            "watched_symbols": ["BTCUSDT"],
            "watchlist_revision": 0,
            "strategies": [],
            "setups": [current, old, other_interval, other_family],
            "limitations": [],
        },
    )
    text, refs, _ = read_brain(
        None, organization_id=uuid4(), message="Current Nested 15m setup state"
    )
    assert [ref.record_id for ref in refs] == [current["setup_id"]]
    assert "FORMING" in text and "EXPIRED" not in text
    assert "order_flow=UNSUPPORTED" in text
    assert "Insufficient history" in text
