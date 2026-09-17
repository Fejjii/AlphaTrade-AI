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
from app.market_contracts.hashing import semantic_content_hash, with_content_hash
from app.market_contracts.identity import (
    ProviderProvenance,
    binance_usdm_btcusdt,
    require_instrument,
    require_perpetual,
)
from app.market_contracts.observation import observation_from_ohlcv
from app.market_contracts.ohlcv import (
    OhlcvBar,
    build_ohlcv_bar,
    observation_id_for,
    require_closed_series,
)
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
    assert first.observation_id == observation_id_for(
        bar.source_event_id, finality=bar.finality, revision=bar.revision
    )
    assert observation_id_for(bar.source_event_id) != first.observation_id


def _forming_bar() -> OhlcvBar:
    return build_ohlcv_bar(
        instrument=binance_usdm_btcusdt(),
        timeframe=Timeframe.M15,
        interval_start=TRIGGER_OPEN,
        open_=Decimal("100000"),
        high=Decimal("100010"),
        low=Decimal("99990"),
        close=Decimal("100005"),
        base_volume=Decimal("10"),
        quote_volume=Decimal("1000000"),
        evaluated_at=TRIGGER_OPEN + timedelta(minutes=5),
        grace=timedelta(0),
        provider_complete=False,
        revision=1,
    )


def test_forming_and_final_observations_have_distinct_append_ids() -> None:
    forming_bar = _forming_bar()
    final_bar = closed_bar()
    assert forming_bar.source_event_id == final_bar.source_event_id
    forming = observation_from_ohlcv(
        forming_bar,
        identity=identity(),
        observed_at=EVALUATED_AT,
        receive_time=EVALUATED_AT,
        freshness_state=FreshnessState.FRESH,
    )
    final = observation_from_ohlcv(
        final_bar,
        identity=identity(),
        observed_at=EVALUATED_AT,
        receive_time=EVALUATED_AT,
        freshness_state=FreshnessState.FRESH,
    )
    assert forming.finality is Finality.FORMING
    assert final.finality is Finality.FINAL
    assert forming.observation_id != final.observation_id
    assert forming.observation_id == observation_id_for(
        forming_bar.source_event_id, finality=Finality.FORMING, revision=1
    )
    assert final.observation_id == observation_id_for(
        final_bar.source_event_id, finality=Finality.FINAL, revision=1
    )


def test_corrected_revision_has_distinct_observation_id() -> None:
    first_bar = closed_bar(revision=1)
    corrected_bar = with_content_hash(
        first_bar.model_copy(
            update={
                "revision": 2,
                "finality": Finality.CORRECTED,
                "content_hash": "0" * 64,
            }
        )
    )
    assert first_bar.source_event_id == corrected_bar.source_event_id
    first = observation_from_ohlcv(
        first_bar,
        identity=identity(),
        observed_at=EVALUATED_AT,
        receive_time=EVALUATED_AT,
        freshness_state=FreshnessState.FRESH,
    )
    corrected = observation_from_ohlcv(
        corrected_bar,
        identity=identity(),
        observed_at=EVALUATED_AT,
        receive_time=EVALUATED_AT,
        freshness_state=FreshnessState.FRESH,
    )
    assert first.observation_id != corrected.observation_id
    assert first.revision == 1
    assert corrected.revision == 2
    assert corrected.finality is Finality.CORRECTED


def test_observation_id_replay_of_same_revision_is_stable() -> None:
    bar = closed_bar(revision=2)
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
    assert first.observation_id == second.observation_id
    assert first.observation_id == observation_id_for(
        bar.source_event_id, finality=bar.finality, revision=2
    )
