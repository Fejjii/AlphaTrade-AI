"""OKX USDT-swap evidence and Binance primary failover. No network. No arming."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from app.core.config import Settings
from app.evidence_pipeline.current_price import quote_current_price
from app.evidence_pipeline.watcher_port import _reconcile_monitor_and_assembled
from app.market_contracts.adapters.factory import resolve_perpetual_evidence_source
from app.market_contracts.adapters.failover import FailoverPerpetualSource
from app.market_contracts.adapters.okx_usdt_swap import OkxUsdtSwapPerpetualSource
from app.market_contracts.cvd import accumulate_signed_quote
from app.market_contracts.enums import SourceFamily, VenueId
from app.market_contracts.errors import (
    EvidenceSourceSwitchRequiredError,
    GapDetectedError,
    IncompleteTradeWindowError,
    RateLimitedError,
    SpotFallbackRejectedError,
    StaleEvidenceError,
    UpstreamBanError,
)
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.freshness import evaluate_freshness, first_slice_freshness_policy
from app.market_contracts.identity import binance_usdm_btcusdt, okx_usdt_swap_btcusdt
from app.market_monitor.backoff import BackoffPolicy
from app.market_monitor.monitor import PerpetualMarketMonitor
from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.schemas.common import Timeframe
from app.watcher.errors import WatcherEvidenceUnavailableError

T0 = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
_INST = "BTC-USDT-SWAP"


def _identity():
    return first_slice_identity(
        timeframe=Timeframe.M15,
        replay=False,
        is_live=True,
        instrument=okx_usdt_swap_btcusdt(),
    )


def _trade(trade_id: int, ts_ms: int, *, side: str = "buy", sz: str = "2") -> dict[str, str]:
    return {
        "instId": _INST,
        "tradeId": str(trade_id),
        "px": "100",
        "sz": sz,
        "side": side,
        "ts": str(ts_ms),
    }


def _candle(start_ms: int, *, confirm: str) -> list[str]:
    return [
        str(start_ms),
        "100",
        "110",
        "90",
        "105",
        "10",
        "0.10",
        "10.5",
        confirm,
    ]


def _source(handler: object, *, max_pages: int = 4) -> OkxUsdtSwapPerpetualSource:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return OkxUsdtSwapPerpetualSource(
        base_url="https://www.okx.com",
        timeout_seconds=2.0,
        transport=transport,
        max_retries=0,
        max_trade_pages=max_pages,
    )


def test_ohlcv_volume_and_provenance_exclude_forming_candles() -> None:
    start = int((T0 - timedelta(minutes=30)).timestamp() * 1000)
    forming = int(T0.timestamp() * 1000)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert "BTC-USDT-SWAP" in str(request.url)
        assert "BTC-USDT&" not in str(request.url)
        return httpx.Response(
            200,
            json={
                "code": "0",
                "data": [_candle(forming, confirm="0"), _candle(start, confirm="1")],
            },
        )

    source = _source(handler)
    series = source.fetch_closed_ohlcv(
        identity=_identity(),
        instrument=okx_usdt_swap_btcusdt(),
        timeframe=Timeframe.M15,
        min_final_bars=1,
        evaluated_at=T0,
    )
    source.close()
    assert len(series.bars) == 1
    assert series.bars[0].base_volume == Decimal("0.10")
    assert series.bars[0].quote_volume == Decimal("10.5")
    assert series.identity.venue is VenueId.OKX
    assert series.identity.source.family is SourceFamily.OKX_USDT_SWAP_PUBLIC
    assert series.identity.provenance.fallback_used is False
    assert series.identity.provenance.is_live is True


def test_cvd_uses_taker_side_and_contract_multiplier() -> None:
    start = T0 - timedelta(seconds=5)
    start_ms = int(start.timestamp() * 1000)
    rows = [
        _trade(11, start_ms + 2000, side="sell", sz="1"),
        _trade(10, start_ms + 1000, side="buy", sz="2"),
        _trade(9, start_ms - 1000, side="buy", sz="9"),
    ]

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "0", "data": rows})

    source = _source(handler)
    batch = source.fetch_ordered_trades(
        identity=_identity(),
        instrument=okx_usdt_swap_btcusdt(),
        start=start,
        end=T0,
        source_connection_id=uuid4(),
        receive_at=T0,
    )
    source.close()
    signed, total = accumulate_signed_quote(batch.trades)
    # buy 2 contracts * 100 * 0.01, sell 1 contract * 100 * 0.01
    assert signed == Decimal("1")
    assert total == Decimal("3")
    assert batch.identity.provenance.provider_name == "okx-usdt-swap-perpetual"
    assert "binance" not in batch.identity.instrument.instrument_id


def test_gap_and_unproven_window_do_not_fabricate() -> None:
    start = T0 - timedelta(seconds=5)
    start_ms = int(start.timestamp() * 1000)

    def gapped(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": "0",
                "data": [
                    _trade(12, start_ms + 1500),
                    _trade(10, start_ms + 500),
                    _trade(9, start_ms - 1000),
                ],
            },
        )

    source = _source(gapped)
    with pytest.raises(GapDetectedError):
        source.fetch_ordered_trades(
            identity=_identity(),
            instrument=okx_usdt_swap_btcusdt(),
            start=start,
            end=T0,
            source_connection_id=uuid4(),
            receive_at=T0,
        )
    source.close()

    def short(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": "0", "data": [_trade(3, start_ms + 1000)]},
        )

    short_source = _source(short, max_pages=1)
    with pytest.raises(IncompleteTradeWindowError):
        short_source.fetch_ordered_trades(
            identity=_identity(),
            instrument=okx_usdt_swap_btcusdt(),
            start=start,
            end=T0,
            source_connection_id=uuid4(),
            receive_at=T0,
        )
    short_source.close()


def test_spot_row_is_rejected() -> None:
    start = T0 - timedelta(seconds=5)
    row = _trade(4, int(start.timestamp() * 1000) + 1000)
    row["instId"] = "BTC-USDT"

    def handler(_request: httpx.Request) -> httpx.Response:
        older = _trade(3, int(start.timestamp() * 1000) - 1)
        return httpx.Response(200, json={"code": "0", "data": [row, older]})

    source = _source(handler)
    with pytest.raises(SpotFallbackRejectedError):
        source.fetch_ordered_trades(
            identity=_identity(),
            instrument=okx_usdt_swap_btcusdt(),
            start=start,
            end=T0,
            source_connection_id=uuid4(),
            receive_at=T0,
        )
    source.close()


def test_outage_and_rate_limit_fail_closed() -> None:
    def down(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    source = _source(down)
    outage = source.status()
    source.close()
    assert outage.health is ProviderHealth.UNAVAILABLE
    assert outage.using_fallback is False
    assert outage.is_mock is False

    def limited(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "1"}, json={"code": "50011"})

    limited_source = _source(limited)
    limited_status = limited_source.status()
    limited_source.close()
    assert limited_status.using_fallback is False
    assert limited_status.health is ProviderHealth.UNAVAILABLE

    def coded(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "50011", "data": []})

    coded_source = _source(coded)
    with pytest.raises(RateLimitedError):
        coded_source.fetch_closed_ohlcv(
            identity=_identity(),
            instrument=okx_usdt_swap_btcusdt(),
            timeframe=Timeframe.M15,
            min_final_bars=1,
            evaluated_at=T0,
        )
    coded_source.close()


def test_stale_trade_fails_freshness() -> None:
    start = T0 - timedelta(seconds=5)
    fresh_ms = int((T0 - timedelta(seconds=1)).timestamp() * 1000)
    proof_ms = int((T0 - timedelta(seconds=15)).timestamp() * 1000)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": "0", "data": [_trade(8, fresh_ms), _trade(7, proof_ms)]},
        )

    source = _source(handler)
    batch = source.fetch_ordered_trades(
        identity=_identity(),
        instrument=okx_usdt_swap_btcusdt(),
        start=start,
        end=T0,
        source_connection_id=uuid4(),
        receive_at=T0,
    )
    source.close()
    later = T0 + timedelta(seconds=30)
    with pytest.raises(StaleEvidenceError):
        evaluate_freshness(
            source_time=batch.trades[-1].event_timestamp,
            evaluated_at=later,
            policy=first_slice_freshness_policy(),
            require_fresh=True,
        )
    quote = quote_current_price(
        _source(handler),
        identity=_identity(),
        instrument=okx_usdt_swap_btcusdt(),
        evaluated_at=T0,
        connection_id=uuid4(),
        replay=False,
    )
    assert quote.usable_as_current_market_price is True
    assert quote.fallback_used is False
    assert quote.source_family is SourceFamily.OKX_USDT_SWAP_PUBLIC


class _BanPrimary:
    name = "binance-usdm-perpetual"
    kind = ProviderKind.MARKET_DATA

    def __init__(self) -> None:
        self.fetches = 0
        self._healthy = False

    def fetch_closed_ohlcv(self, **_kwargs: object) -> object:
        self.fetches += 1
        raise UpstreamBanError("banned", retry_after_seconds=90)

    def fetch_ordered_trades(self, **_kwargs: object) -> object:
        self.fetches += 1
        raise UpstreamBanError("banned", retry_after_seconds=90)

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=ProviderHealth.HEALTHY if self._healthy else ProviderHealth.DEGRADED,
            using_fallback=False,
            is_mock=False,
            detail="primary",
        )


def test_provider_switch_keeps_okx_provenance_and_can_recover() -> None:
    primary = _BanPrimary()
    start = T0 - timedelta(seconds=4)
    start_ms = int(start.timestamp() * 1000)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.url.path.endswith("/time"):
            return httpx.Response(200, json={"code": "0", "data": [{"ts": "1"}]})
        if request.url.path.endswith("/candles"):
            closed = int((T0 - timedelta(minutes=30)).timestamp() * 1000)
            return httpx.Response(
                200,
                json={"code": "0", "data": [_candle(closed, confirm="1")]},
            )
        return httpx.Response(
            200,
            json={"code": "0", "data": [_trade(5, start_ms + 1000), _trade(4, start_ms - 1000)]},
        )

    secondary = _source(handler)
    router = FailoverPerpetualSource(
        primary,  # type: ignore[arg-type]
        secondary,
        primary_instrument=binance_usdm_btcusdt(),
        secondary_instrument=okx_usdt_swap_btcusdt(),
    )
    with pytest.raises(EvidenceSourceSwitchRequiredError) as switched:
        router.fetch_ordered_trades(
            identity=first_slice_identity(
                timeframe=Timeframe.M15,
                replay=False,
                is_live=True,
                instrument=binance_usdm_btcusdt(),
            ),
            instrument=binance_usdm_btcusdt(),
            start=start,
            end=T0,
            source_connection_id=uuid4(),
            receive_at=T0,
        )
    assert switched.value.instrument == okx_usdt_swap_btcusdt()
    assert calls["n"] == 0
    batch = router.fetch_ordered_trades(
        identity=_identity(),
        instrument=okx_usdt_swap_btcusdt(),
        start=start,
        end=T0,
        source_connection_id=uuid4(),
        receive_at=T0,
    )
    assert batch.identity.venue is VenueId.OKX
    assert primary.fetches == 1
    with pytest.raises(EvidenceSourceSwitchRequiredError):
        router.fetch_ordered_trades(
            identity=first_slice_identity(
                timeframe=Timeframe.M15,
                replay=False,
                is_live=True,
                instrument=binance_usdm_btcusdt(),
            ),
            instrument=binance_usdm_btcusdt(),
            start=start,
            end=T0,
            source_connection_id=uuid4(),
            receive_at=T0,
        )
    primary._healthy = True
    recovered = router.try_recover_primary()
    assert recovered == binance_usdm_btcusdt()
    assert router.using_secondary is False
    secondary.close()


def test_monitor_switch_publishes_okx_not_a_binance_price() -> None:
    primary = _BanPrimary()
    inside_ms = int((T0 - timedelta(seconds=2)).timestamp() * 1000)
    proof_ms = int((T0 - timedelta(seconds=11)).timestamp() * 1000)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/candles"):
            closed = int((T0 - timedelta(minutes=30)).timestamp() * 1000)
            return httpx.Response(200, json={"code": "0", "data": [_candle(closed, confirm="1")]})
        return httpx.Response(
            200,
            json={
                "code": "0",
                "data": [
                    _trade(6, inside_ms, side="buy"),
                    _trade(5, proof_ms, side="buy"),
                ],
            },
        )

    router = FailoverPerpetualSource(
        primary,  # type: ignore[arg-type]
        _source(handler),
        primary_instrument=binance_usdm_btcusdt(),
        secondary_instrument=okx_usdt_swap_btcusdt(),
    )
    monitor = PerpetualMarketMonitor(
        router,  # type: ignore[arg-type]
        replay=False,
        backoff=BackoffPolicy(initial_seconds=0.01, max_seconds=1.0),
        clock=lambda: T0,
        poll_seconds=0.01,
    )
    snapshot = monitor.tick("BTCUSDT", now=T0)
    assert snapshot.source_family is SourceFamily.OKX_USDT_SWAP_PUBLIC
    assert snapshot.instrument_id == okx_usdt_swap_btcusdt().instrument_id
    assert snapshot.fallback_used is False
    assert snapshot.current_price is not None
    assert snapshot.current_price.provider_name == "okx-usdt-swap-perpetual"
    assert primary.fetches == 1
    _reconcile_monitor_and_assembled(snapshot, False, SourceFamily.OKX_USDT_SWAP_PUBLIC)
    with pytest.raises(WatcherEvidenceUnavailableError) as exc:
        _reconcile_monitor_and_assembled(snapshot, False, SourceFamily.BINANCE_USDM_FUTURES_PUBLIC)
    assert exc.value.reason_code == "wrong_source"


def test_factory_selects_secondary_without_enabling_trading() -> None:
    settings = Settings(
        environment="local",
        execution_mode="paper",
        enable_real_trading=False,
        exchange_mode="paper_internal",
        provider_mode="mock",
        perpetual_evidence_source="binance_usdm",
        perpetual_evidence_secondary_source="okx_usdt_swap",
        market_data_futures_base_url="https://fapi.binance.com",
        okx_swap_base_url="https://www.okx.com",
    )
    source = resolve_perpetual_evidence_source(settings)
    assert isinstance(source, FailoverPerpetualSource)
    assert source.active_instrument().venue is VenueId.BINANCE
    assert settings.enable_real_trading is False
    with pytest.raises(ValueError, match="spot"):
        Settings(
            environment="local",
            perpetual_evidence_source="spot",
            jwt_secret="x" * 40,
        )
