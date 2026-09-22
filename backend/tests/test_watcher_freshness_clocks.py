"""Monitoring clocks stay independent of OHLCV availability and trade coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.market_contracts.adapters.replay import ReplayPerpetualSource
from app.market_contracts.enums import DataCompleteness
from app.market_contracts.first_slice import CANONICAL_EVALUATED_AT, CANONICAL_TRIGGER_INTERVAL_END
from app.market_contracts.freshness import FIRST_SLICE_TRADE_MAX_AGE_SECONDS
from app.market_monitor.backoff import BackoffPolicy
from app.market_monitor.monitor import PerpetualMarketMonitor
from app.schemas.common import Timeframe
from app.services.watcher_monitoring_service import _market_freshness
from tests.support.live_market_monitor import ScriptedPerpetualSource
from tests.support.phase5_market import closed_bar, consecutive_bars, trade


def _monitor(source: object, *, replay: bool, now: datetime) -> object:
    return PerpetualMarketMonitor(
        source,  # type: ignore[arg-type]
        replay=replay,
        backoff=BackoffPolicy(initial_seconds=0.25, max_seconds=4.0),
        poll_seconds=0.01,
        clock=lambda: now,
    )


def test_partial_ohlcv_is_not_closed_candle_finality() -> None:
    now = datetime(2026, 9, 21, 14, 0, tzinfo=UTC)
    last_open = now - timedelta(minutes=30)
    bars = [
        closed_bar(
            open_time=last_open - timedelta(minutes=15),
            index=0,
            evaluated_at=now,
            timeframe=Timeframe.M15,
        ),
        closed_bar(open_time=last_open, index=1, evaluated_at=now, timeframe=Timeframe.M15),
    ]
    source = ScriptedPerpetualSource(replay=False, bars_15m=bars)
    source.enqueue(
        [
            trade(
                sequence=10,
                price="101234.7",
                quantity="0.01",
                buyer_is_maker=False,
                event_time=now - timedelta(seconds=1),
                receive_at=now - timedelta(seconds=1),
            )
        ]
    )
    monitor = _monitor(source, replay=False, now=now)
    snapshot = monitor.tick("BTCUSDT", now=now)  # type: ignore[attr-defined]
    assert snapshot.ohlcv.available is True
    assert snapshot.ohlcv.completeness_15m is not DataCompleteness.COMPLETE
    freshness = _market_freshness(
        observation=None,
        monitor_snapshot=snapshot,
        stale_after_minutes=60,
        now=now,
    )
    assert freshness.closed_candle_final is False
    assert freshness.historical_evidence_valid is False
    assert freshness.quote_max_age_seconds == FIRST_SLICE_TRADE_MAX_AGE_SECONDS
    assert freshness.stale_after_minutes is None
    assert freshness.legacy_scanner_stale_after_minutes is None


def test_complete_coverage_is_not_historical_validity_inside_quote_window() -> None:
    moment = CANONICAL_EVALUATED_AT
    monitor = _monitor(ReplayPerpetualSource(), replay=True, now=moment)
    snapshot = monitor.tick("BTCUSDT", now=moment)  # type: ignore[attr-defined]
    assert snapshot.ohlcv.available is True
    assert snapshot.ohlcv.latest_15m_final is True
    assert snapshot.ohlcv.completeness_15m is DataCompleteness.COMPLETE
    assert snapshot.coverage.completeness is DataCompleteness.COMPLETE
    assert snapshot.ohlcv.latest_15m_end == CANONICAL_TRIGGER_INTERVAL_END
    freshness = _market_freshness(
        observation=None,
        monitor_snapshot=snapshot,
        stale_after_minutes=60,
        now=moment,
    )
    assert freshness.closed_candle_final is True
    assert freshness.historical_evidence_valid is False
    assert freshness.quote_fresh is False
    assert freshness.usable_as_current_market_price is False
    assert freshness.quote_max_age_seconds == 10
    assert freshness.trade_stream_fresh is True
    assert freshness.setup_lifetime_expired is None


def test_quote_freshness_uses_the_ten_second_live_mark_policy() -> None:
    now = datetime(2026, 9, 21, 14, 0, tzinfo=UTC)
    bars = consecutive_bars(2, last_open=now - timedelta(minutes=15))
    source = ScriptedPerpetualSource(replay=False, bars_15m=bars)
    source.enqueue(
        [
            trade(
                sequence=11,
                price="101000.1",
                quantity="0.02",
                buyer_is_maker=False,
                event_time=now - timedelta(seconds=2),
                receive_at=now - timedelta(seconds=2),
            )
        ]
    )
    monitor = _monitor(source, replay=False, now=now)
    fresh = monitor.tick("BTCUSDT", now=now)  # type: ignore[attr-defined]
    fresh_clocks = _market_freshness(
        observation=None,
        monitor_snapshot=fresh,
        stale_after_minutes=60,
        now=now,
    )
    assert fresh.current_price is not None
    assert fresh.current_price.usable_as_current_market_price is True
    assert fresh_clocks.quote_fresh is True
    assert fresh_clocks.quote_max_age_seconds == 10

    later = now + timedelta(seconds=12)
    stale = monitor.tick("BTCUSDT", now=later)  # type: ignore[attr-defined]
    stale_clocks = _market_freshness(
        observation=None,
        monitor_snapshot=stale,
        stale_after_minutes=60,
        now=later,
    )
    assert stale_clocks.quote_fresh is False
    assert stale_clocks.usable_as_current_market_price is False
    assert stale_clocks.quote_max_age_seconds == 10
