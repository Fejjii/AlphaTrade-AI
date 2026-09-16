"""Phase 5 market identities, closed OHLCV, hashes, and provenance."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from app.market_contracts.enums import Finality, FreshnessState, MarketType, SourceFamily, VenueId
from app.market_contracts.errors import (
    FormingCandleError,
    GapDetectedError,
    WrongInstrumentError,
    WrongMarketError,
)
from app.market_contracts.first_slice import (
    FIRST_SLICE_MIN_FINAL_4H,
    FIRST_SLICE_MIN_FINAL_15M,
    first_slice_spec,
)
from app.market_contracts.hashing import semantic_content_hash
from app.market_contracts.identity import (
    ProviderProvenance,
    binance_usdm_btcusdt,
    require_instrument,
    require_perpetual,
)
from app.market_contracts.observation import observation_from_ohlcv
from app.market_contracts.ohlcv import build_ohlcv_bar, require_closed_series
from app.schemas.common import Timeframe
from tests.support.phase5_market import (
    EVALUATED_AT,
    TRIGGER_OPEN,
    closed_bar,
    consecutive_bars,
    eth_instrument,
    identity,
    spot_identity,
)


def test_canonical_first_slice_instrument() -> None:
    spec = first_slice_spec()
    instrument = spec.instrument
    assert instrument.provider_symbol == "BTCUSDT"
    assert instrument.market_type is MarketType.PERPETUAL
    assert instrument.venue is VenueId.BINANCE
    assert instrument.instrument_id == "binance:usdm_futures:perpetual:BTCUSDT"
    assert spec.min_final_trigger_bars == FIRST_SLICE_MIN_FINAL_15M
    assert spec.min_final_context_bars == FIRST_SLICE_MIN_FINAL_4H
    assert spec.trigger_timeframe is Timeframe.M15
    assert spec.context_timeframe is Timeframe.H4


def test_closed_candle_validation() -> None:
    bars = consecutive_bars(3)
    series = require_closed_series(
        bars,
        identity=identity(),
        timeframe=Timeframe.M15,
        evaluated_at=EVALUATED_AT,
        min_bars=3,
    )
    assert all(bar.finality is Finality.FINAL for bar in series.bars)
    assert all(bar.provider_complete for bar in series.bars)
    assert series.bars[-1].interval_start == TRIGGER_OPEN


def test_forming_candle_rejection() -> None:
    forming_at = TRIGGER_OPEN + timedelta(minutes=5)
    bar = build_ohlcv_bar(
        instrument=binance_usdm_btcusdt(),
        timeframe=Timeframe.M15,
        interval_start=TRIGGER_OPEN,
        open_=Decimal("100000"),
        high=Decimal("100010"),
        low=Decimal("99990"),
        close=Decimal("100005"),
        base_volume=Decimal("10"),
        quote_volume=Decimal("1000000"),
        evaluated_at=forming_at,
        grace=timedelta(0),
    )
    assert bar.finality is Finality.FORMING
    with pytest.raises(FormingCandleError):
        require_closed_series(
            [bar],
            identity=identity(),
            timeframe=Timeframe.M15,
            evaluated_at=forming_at,
            min_bars=1,
        )


def test_wrong_market_rejection() -> None:
    with pytest.raises(WrongMarketError):
        require_perpetual(spot_identity())


def test_wrong_instrument_rejection() -> None:
    market = identity()
    with pytest.raises(WrongInstrumentError):
        require_instrument(market, eth_instrument())


def test_ohlcv_gap_detection() -> None:
    first = closed_bar(open_time=TRIGGER_OPEN - timedelta(minutes=30), index=0)
    third = closed_bar(open_time=TRIGGER_OPEN, index=2)
    with pytest.raises(GapDetectedError, match="interval gap"):
        require_closed_series(
            [first, third],
            identity=identity(),
            timeframe=Timeframe.M15,
            evaluated_at=EVALUATED_AT,
            min_bars=2,
        )


def test_duplicate_ohlcv_rejected() -> None:
    bar = closed_bar()
    with pytest.raises(GapDetectedError, match="Duplicate"):
        require_closed_series(
            [bar, bar],
            identity=identity(),
            timeframe=Timeframe.M15,
            evaluated_at=EVALUATED_AT,
            min_bars=2,
        )


def test_content_hash_stability() -> None:
    left = closed_bar()
    right = closed_bar()
    assert left.content_hash == right.content_hash
    changed = closed_bar(index=9)
    assert changed.content_hash != left.content_hash
    again = semantic_content_hash(left, extra_exclude=frozenset({"content_hash"}))
    assert again == left.content_hash


def test_provider_provenance_forbids_fallback() -> None:
    with pytest.raises(ValueError, match="fallback"):
        ProviderProvenance(
            provider_name="binance-usdm-perpetual",
            source_family=SourceFamily.BINANCE_USDM_FUTURES_PUBLIC,
            adapter_version="binance-usdm-perpetual/v1",
            is_live=True,
            fallback_used=True,
            is_mock=False,
        )


def test_observation_envelope_excludes_recorded_time_from_hash() -> None:
    bar = closed_bar()
    first = observation_from_ohlcv(
        bar,
        identity=identity(),
        observed_at=EVALUATED_AT,
        receive_time=EVALUATED_AT,
        freshness_state=FreshnessState.FRESH,
    )
    second = observation_from_ohlcv(
        bar,
        identity=identity(),
        observed_at=EVALUATED_AT,
        receive_time=EVALUATED_AT,
        freshness_state=FreshnessState.FRESH,
    )
    assert first.content_hash == second.content_hash
    assert first.privacy_class.value == "public_market_data"
    assert first.observation_id == second.observation_id
