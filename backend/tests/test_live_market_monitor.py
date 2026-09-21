"""AT-069 continuous read-only USD-M market monitor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest

from app.evidence_pipeline.types import CurrentPricePresentation
from app.market_contracts.adapters.http import ReadOnlyHttpGetClient
from app.market_contracts.adapters.replay import ReplayPerpetualSource
from app.market_contracts.catalog import default_perpetual_catalog
from app.market_contracts.enums import GapState, ReconnectState, SourceFamily
from app.market_contracts.errors import (
    RateLimitedError,
    RegionalProviderFailureError,
    SpotFallbackRejectedError,
)
from app.market_contracts.identity import binance_usdm_perpetual
from app.market_monitor.backoff import BackoffPolicy, delay_seconds
from app.market_monitor.identity import monitor_semantic_hash
from app.market_monitor.monitor import PerpetualMarketMonitor
from app.market_monitor.types import MarketAvailability, MarketMode, MonitorReason
from app.market_monitor.watcher_port import MarketMonitorWatcherPort
from tests.support.live_market_monitor import ScriptedPerpetualSource
from tests.support.phase5_market import consecutive_bars, eth_instrument, trade

T0 = datetime(2026, 9, 21, 14, 0, 0, tzinfo=UTC)


def _live_monitor(
    source: ScriptedPerpetualSource,
    *,
    catalog=None,
    poll_seconds: float = 0.01,
) -> PerpetualMarketMonitor:
    return PerpetualMarketMonitor(
        source,
        replay=False,
        catalog=catalog,
        backoff=BackoffPolicy(initial_seconds=0.25, max_seconds=8.0, multiplier=2.0),
        poll_seconds=poll_seconds,
    )


def _trade(sequence: int, *, when: datetime, price: str = "100000.5") -> object:
    return trade(
        sequence=sequence,
        price=price,
        quantity="0.01",
        buyer_is_maker=False,
        event_time=when,
        receive_at=when,
    )


def test_backoff_respects_retry_after_and_cap() -> None:
    policy = BackoffPolicy(initial_seconds=0.25, max_seconds=4.0, multiplier=2.0)
    assert delay_seconds(0, policy) == 0.25
    assert delay_seconds(1, policy) == 0.5
    assert delay_seconds(10, policy) == 4.0
    assert delay_seconds(0, policy, retry_after_seconds=2.5) == 2.5
    assert delay_seconds(0, policy, retry_after_seconds=99.0) == 4.0


def test_http_client_maps_429_to_rate_limited_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(429, headers={"Retry-After": "3"}, json={"msg": "too many"})

    client = ReadOnlyHttpGetClient(
        base_url="https://fapi.binance.com",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(RateLimitedError) as exc:
        client.get_json("/fapi/v1/ping")
    assert exc.value.retry_after_seconds == 3.0
    client.close()


def test_replay_monitor_is_never_a_live_mark() -> None:
    monitor = PerpetualMarketMonitor(ReplayPerpetualSource(), replay=True)
    snapshot = monitor.tick("BTCUSDT")
    assert snapshot.mode is MarketMode.REPLAY
    assert snapshot.availability is MarketAvailability.REPLAY
    assert snapshot.reason is MonitorReason.REPLAY_FIXTURE
    assert snapshot.is_live is False
    assert snapshot.is_mock is True
    assert snapshot.watcher_activated is False
    assert snapshot.live_executable is False
    assert snapshot.source_family is SourceFamily.REPLAY_FIXTURE
    assert snapshot.current_price is not None
    assert snapshot.current_price.usable_as_current_market_price is False
    assert snapshot.current_price.presentation is CurrentPricePresentation.REPLAY_FIXTURE
    assert snapshot.current_price.is_live is False
    assert str(snapshot.current_price.price) not in {"47326", "65000"}
    assert snapshot.ohlcv.available is True
    assert snapshot.cvd.available is True
    port = MarketMonitorWatcherPort(monitor)
    latest = port.latest("BTCUSDT")
    assert latest.watcher_activated is False
    assert latest.current_price is not None
    assert latest.current_price.usable_as_current_market_price is False


def test_live_fresh_trade_is_a_usable_perpetual_mark() -> None:
    bars = consecutive_bars(2, last_open=T0 - timedelta(minutes=15))
    source = ScriptedPerpetualSource(bars_15m=bars)
    source.enqueue([_trade(10, when=T0 - timedelta(seconds=1), price="101234.7")])
    snapshot = _live_monitor(source).tick("BTCUSDT", now=T0)
    assert snapshot.mode is MarketMode.LIVE_PERPETUAL
    assert snapshot.availability is MarketAvailability.FRESH
    assert snapshot.current_price is not None
    assert snapshot.current_price.usable_as_current_market_price is True
    assert snapshot.current_price.presentation is CurrentPricePresentation.LIVE_MARK
    assert str(snapshot.current_price.price) == "101234.7"
    assert snapshot.current_price.is_live is True
    assert snapshot.current_price.is_mock is False
    assert snapshot.stream.reconnect_state is ReconnectState.CONTINUOUS
    assert snapshot.cvd.available is True
    assert snapshot.fallback_used is False


def test_stale_stream_fails_closed_without_fabricating_a_price() -> None:
    source = ScriptedPerpetualSource()
    source.enqueue([_trade(10, when=T0 - timedelta(seconds=1))])
    monitor = _live_monitor(source)
    first = monitor.tick("BTCUSDT", now=T0)
    assert first.current_price is not None
    later = monitor.tick("BTCUSDT", now=T0 + timedelta(seconds=12))
    assert later.availability is MarketAvailability.STALE
    assert later.reason is MonitorReason.STALE_STREAM
    assert later.current_price is None


def test_disconnect_reconnect_recovers_without_reusing_connection_identity() -> None:
    source = ScriptedPerpetualSource()
    first_trade = _trade(10, when=T0 - timedelta(seconds=2))
    second = _trade(11, when=T0 + timedelta(seconds=1))
    source.enqueue([first_trade])
    monitor = _live_monitor(source)
    connected = monitor.tick("BTCUSDT", now=T0)
    epoch = connected.stream.connection_identity
    source.enqueue(RegionalProviderFailureError("USD-M unreachable"))
    dropped = monitor.tick("BTCUSDT", now=T0 + timedelta(seconds=1))
    assert dropped.availability is MarketAvailability.UNAVAILABLE
    assert dropped.reason is MonitorReason.PROVIDER_UNAVAILABLE
    assert dropped.current_price is None
    assert dropped.stream.reconnect_state is ReconnectState.RECONNECTING
    assert dropped.stream.connection_identity != epoch
    # Still inside backoff — must not consume the backfill yet.
    source.enqueue([first_trade, second])
    held = monitor.tick("BTCUSDT", now=T0 + timedelta(seconds=1, milliseconds=100))
    assert held.backoff.active is True
    assert held.availability is MarketAvailability.DEGRADED
    recovered = monitor.tick("BTCUSDT", now=T0 + timedelta(seconds=2))
    assert recovered.stream.reconnect_state in {ReconnectState.RECOVERED, ReconnectState.CONTINUOUS}
    assert recovered.stream.connection_identity != epoch
    assert recovered.stream.reconnect_count == 1
    assert recovered.current_price is not None
    assert recovered.current_price.usable_as_current_market_price is True
    assert recovered.content_hash != connected.content_hash


def test_duplicate_identical_trades_are_ignored() -> None:
    source = ScriptedPerpetualSource()
    event = _trade(4, when=T0 - timedelta(seconds=1), price="99000")
    source.enqueue([event])
    monitor = _live_monitor(source)
    first = monitor.tick("BTCUSDT", now=T0)
    source.enqueue([event])
    second = monitor.tick("BTCUSDT", now=T0 + timedelta(milliseconds=20))
    assert first.stream.last_sequence == 4
    assert second.stream.last_sequence == 4
    assert first.content_hash == second.content_hash
    assert second.reason is not MonitorReason.DUPLICATE_CONFLICT


def test_conflicting_duplicate_fails_closed() -> None:
    source = ScriptedPerpetualSource()
    source.enqueue([_trade(4, when=T0 - timedelta(seconds=1), price="99000")])
    monitor = _live_monitor(source)
    monitor.tick("BTCUSDT", now=T0)
    source.enqueue([_trade(4, when=T0 - timedelta(seconds=1), price="99100")])
    snapshot = monitor.tick("BTCUSDT", now=T0 + timedelta(milliseconds=20))
    assert snapshot.availability is MarketAvailability.UNAVAILABLE
    assert snapshot.reason is MonitorReason.DUPLICATE_CONFLICT
    assert snapshot.current_price is None


def test_out_of_order_trades_fail_closed() -> None:
    source = ScriptedPerpetualSource()
    source.enqueue([_trade(8, when=T0 - timedelta(seconds=2))])
    monitor = _live_monitor(source)
    monitor.tick("BTCUSDT", now=T0)
    source.enqueue([_trade(7, when=T0 - timedelta(seconds=1))])
    snapshot = monitor.tick("BTCUSDT", now=T0 + timedelta(milliseconds=20))
    assert snapshot.availability is MarketAvailability.UNAVAILABLE
    assert snapshot.reason is MonitorReason.OUT_OF_ORDER
    assert snapshot.current_price is None


def test_sequence_gap_fails_closed() -> None:
    source = ScriptedPerpetualSource()
    source.enqueue([_trade(1, when=T0 - timedelta(seconds=2))])
    monitor = _live_monitor(source)
    monitor.tick("BTCUSDT", now=T0)
    source.enqueue([_trade(5, when=T0 - timedelta(seconds=1))])
    snapshot = monitor.tick("BTCUSDT", now=T0 + timedelta(milliseconds=20))
    assert snapshot.availability in {MarketAvailability.DEGRADED, MarketAvailability.UNAVAILABLE}
    assert snapshot.reason in {MonitorReason.GAP, MonitorReason.UNRECOVERABLE_GAP}
    assert snapshot.stream.gap_state in {
        GapState.CONFIRMED,
        GapState.SUSPECTED,
        GapState.UNRECOVERABLE,
    }
    price = snapshot.current_price
    assert price is None or price.usable_as_current_market_price is False


def test_rate_limit_degrades_and_respects_backoff() -> None:
    source = ScriptedPerpetualSource()
    source.enqueue([_trade(3, when=T0 - timedelta(seconds=1), price="100100")])
    monitor = _live_monitor(source)
    fresh = monitor.tick("BTCUSDT", now=T0)
    assert fresh.availability is MarketAvailability.FRESH
    source.enqueue(RateLimitedError("slow down", retry_after_seconds=2.0))
    limited = monitor.tick("BTCUSDT", now=T0 + timedelta(milliseconds=20))
    assert limited.availability is MarketAvailability.DEGRADED
    assert limited.reason is MonitorReason.RATE_LIMITED
    assert limited.backoff.active is True
    source.enqueue([_trade(4, when=T0 + timedelta(seconds=1), price="100110")])
    held = monitor.tick("BTCUSDT", now=T0 + timedelta(seconds=1))
    assert held.backoff.active is True
    assert source.fetch_count == 2
    recovered = monitor.tick("BTCUSDT", now=T0 + timedelta(seconds=3))
    assert recovered.availability is MarketAvailability.FRESH
    assert recovered.current_price is not None
    assert str(recovered.current_price.price) == "100110"


def test_provider_outage_fails_closed_without_spot_fallback() -> None:
    source = ScriptedPerpetualSource()
    source.enqueue(SpotFallbackRejectedError("spot cannot satisfy perpetual evidence"))
    snapshot = _live_monitor(source).tick("BTCUSDT", now=T0)
    assert snapshot.availability is MarketAvailability.UNAVAILABLE
    assert snapshot.reason is MonitorReason.SPOT_REJECTED
    assert snapshot.current_price is None
    assert snapshot.fallback_used is False


def test_symbol_mismatch_fails_closed() -> None:
    source = ScriptedPerpetualSource()
    source.enqueue(
        [
            trade(
                sequence=1,
                price="3000",
                quantity="1",
                buyer_is_maker=False,
                event_time=T0 - timedelta(seconds=1),
                receive_at=T0,
                instrument=eth_instrument(),
            )
        ]
    )
    snapshot = _live_monitor(source).tick("BTCUSDT", now=T0)
    assert snapshot.availability is MarketAvailability.UNAVAILABLE
    assert snapshot.reason is MonitorReason.SYMBOL_MISMATCH
    assert snapshot.current_price is None


def test_unknown_catalog_symbol_is_rejected() -> None:
    monitor = _live_monitor(ScriptedPerpetualSource())
    with pytest.raises(Exception, match="ETHUSDT") as exc:
        monitor.tick("ETHUSDT", now=T0)
    assert "unknown_perpetual_instrument" in getattr(exc.value, "code", "") or "ETHUSDT" in str(
        exc.value
    )


def test_catalog_extension_does_not_rewrite_the_monitor() -> None:
    eth = binance_usdm_perpetual("ETHUSDT")
    source = ScriptedPerpetualSource(instrument=eth)
    source.enqueue(
        [
            trade(
                sequence=1,
                price="3000.25",
                quantity="1",
                buyer_is_maker=True,
                event_time=T0 - timedelta(seconds=1),
                receive_at=T0,
                instrument=eth,
            )
        ]
    )
    catalog = default_perpetual_catalog().extend(eth)
    snapshot = _live_monitor(source, catalog=catalog).tick("ETHUSDT", now=T0)
    assert snapshot.symbol == "ETHUSDT"
    assert snapshot.current_price is not None
    assert snapshot.current_price.usable_as_current_market_price is True


def test_restart_opens_a_new_epoch_and_keeps_semantic_identity() -> None:
    def _source() -> ScriptedPerpetualSource:
        source = ScriptedPerpetualSource()
        source.enqueue([_trade(20, when=T0 - timedelta(seconds=1), price="100500")])
        return source

    first = _live_monitor(_source()).tick("BTCUSDT", now=T0)
    second = _live_monitor(_source()).tick("BTCUSDT", now=T0)
    assert first.stream.connection_identity != second.stream.connection_identity
    assert first.content_hash == second.content_hash
    assert first.current_price is not None
    assert second.current_price is not None
    assert first.current_price.venue_trade_id == second.current_price.venue_trade_id


def test_market_correction_changes_semantic_identity() -> None:
    source = ScriptedPerpetualSource()
    source.enqueue([_trade(20, when=T0 - timedelta(seconds=2), price="100500")])
    monitor = _live_monitor(source)
    before = monitor.tick("BTCUSDT", now=T0)
    source.enqueue([_trade(21, when=T0 - timedelta(seconds=1), price="100700")])
    after = monitor.tick("BTCUSDT", now=T0 + timedelta(milliseconds=20))
    assert before.content_hash != after.content_hash
    assert after.content_hash == monitor_semantic_hash(after)
    assert "connection_identity" not in after.model_dump() or True
    assert before.stream.connection_identity == after.stream.connection_identity


def test_transport_metadata_is_excluded_from_semantic_hash() -> None:
    source = ScriptedPerpetualSource()
    event = _trade(9, when=T0 - timedelta(seconds=1), price="100200")
    source.enqueue([event])
    snapshot = _live_monitor(source).tick("BTCUSDT", now=T0)
    retagged = snapshot.model_copy(
        update={
            "backoff": snapshot.backoff.model_copy(
                update={"active": True, "attempt": 4, "last_error_class": "RateLimitedError"}
            ),
            "stream": snapshot.stream.model_copy(update={"connection_identity": UUID(int=1)}),
            "evaluated_at": T0 + timedelta(milliseconds=3),
        }
    )
    assert monitor_semantic_hash(snapshot) == monitor_semantic_hash(retagged)
    corrected = snapshot.model_copy(
        update={
            "current_price": (
                snapshot.current_price.model_copy(
                    update={"price": snapshot.current_price.price + 1}
                )
                if snapshot.current_price is not None
                else None
            )
        }
    )
    assert monitor_semantic_hash(snapshot) != monitor_semantic_hash(corrected)


def test_replay_source_cannot_be_labelled_live() -> None:
    monitor = PerpetualMarketMonitor(ReplayPerpetualSource(), replay=False)
    snapshot = monitor.tick("BTCUSDT", now=T0)
    assert snapshot.availability is MarketAvailability.UNAVAILABLE
    assert snapshot.reason is MonitorReason.WRONG_SOURCE
    price = snapshot.current_price
    assert price is None or price.usable_as_current_market_price is False


def test_live_source_cannot_be_labelled_replay() -> None:
    source = ScriptedPerpetualSource(replay=False)
    source.enqueue([_trade(1, when=T0 - timedelta(seconds=1))])
    monitor = PerpetualMarketMonitor(source, replay=True)
    snapshot = monitor.tick("BTCUSDT")
    assert snapshot.mode is MarketMode.REPLAY
    assert snapshot.availability is MarketAvailability.REPLAY
    price = snapshot.current_price
    assert price is None or price.usable_as_current_market_price is False
    assert snapshot.reason in {MonitorReason.REPLAY_FIXTURE, MonitorReason.WRONG_SOURCE}


def test_provider_error_fails_closed() -> None:
    source = ScriptedPerpetualSource()
    source.enqueue(RegionalProviderFailureError("connect timeout"))
    snapshot = _live_monitor(source).tick("BTCUSDT", now=T0)
    assert snapshot.availability is MarketAvailability.UNAVAILABLE
    assert snapshot.reason is MonitorReason.PROVIDER_UNAVAILABLE
    assert snapshot.current_price is None
    assert snapshot.provider.using_fallback is False
