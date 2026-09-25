"""Canonical first-slice BTCUSDT perpetual evidence identities and bounds."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import AwareDatetime, Field

from app.market_contracts.enums import SourceFamily, VenueId
from app.market_contracts.identity import (
    ADAPTER_VERSION,
    AGGRESSOR_CONVENTION,
    OKX_ADAPTER_VERSION,
    OKX_AGGRESSOR_CONVENTION,
    EvidenceMarketIdentity,
    InstrumentIdentity,
    ProviderProvenance,
    SourceIdentity,
    binance_usdm_btcusdt,
    require_instrument,
    require_perpetual,
)
from app.market_contracts.models import CanonicalModel
from app.schemas.common import Timeframe

FIRST_SLICE_SYMBOL = "BTCUSDT"
FIRST_SLICE_TRIGGER_TIMEFRAME = Timeframe.M15
FIRST_SLICE_CONTEXT_TIMEFRAME = Timeframe.H4
FIRST_SLICE_MIN_FINAL_15M = 100
FIRST_SLICE_MIN_FINAL_4H = 30
FIRST_SLICE_PATTERN_NAME = (
    "Bearish Liquidity Sweep with CVD Divergence and Aggressive Sell Imbalance at 4h Resistance"
)
FIRST_SLICE_TRADE_FRESHNESS_SECONDS = 10
# Exclusive end of the canonical trigger 15m bar (T).
CANONICAL_TRIGGER_INTERVAL_START = datetime(2026, 1, 15, 16, 0, tzinfo=UTC)
CANONICAL_TRIGGER_INTERVAL_END = datetime(2026, 1, 15, 16, 15, tzinfo=UTC)
CANONICAL_EVALUATED_AT = datetime(2026, 1, 15, 16, 15, 5, tzinfo=UTC)


class FirstSliceSpec(CanonicalModel):
    symbol: str = Field(min_length=2, max_length=16)
    trigger_timeframe: Timeframe
    context_timeframe: Timeframe
    min_final_trigger_bars: int = Field(ge=1)
    min_final_context_bars: int = Field(ge=1)
    pattern_name: str = Field(min_length=8, max_length=200)
    trade_freshness_seconds: int = Field(ge=0)
    instrument: InstrumentIdentity


def first_slice_spec() -> FirstSliceSpec:
    return FirstSliceSpec(
        symbol=FIRST_SLICE_SYMBOL,
        trigger_timeframe=FIRST_SLICE_TRIGGER_TIMEFRAME,
        context_timeframe=FIRST_SLICE_CONTEXT_TIMEFRAME,
        min_final_trigger_bars=FIRST_SLICE_MIN_FINAL_15M,
        min_final_context_bars=FIRST_SLICE_MIN_FINAL_4H,
        pattern_name=FIRST_SLICE_PATTERN_NAME,
        trade_freshness_seconds=FIRST_SLICE_TRADE_FRESHNESS_SECONDS,
        instrument=binance_usdm_btcusdt(),
    )


def okx_usdt_swap_source() -> SourceIdentity:
    return SourceIdentity(
        family=SourceFamily.OKX_USDT_SWAP_PUBLIC,
        provider_name="okx-usdt-swap-perpetual",
        adapter_version=OKX_ADAPTER_VERSION,
        aggressor_convention=OKX_AGGRESSOR_CONVENTION,
    )


def binance_usdm_source(*, replay: bool) -> SourceIdentity:
    if replay:
        return SourceIdentity(
            family=SourceFamily.REPLAY_FIXTURE,
            provider_name="binance-usdm-perpetual-replay",
            adapter_version=ADAPTER_VERSION,
            aggressor_convention=AGGRESSOR_CONVENTION,
        )
    return SourceIdentity(
        family=SourceFamily.BINANCE_USDM_FUTURES_PUBLIC,
        provider_name="binance-usdm-perpetual",
        adapter_version=ADAPTER_VERSION,
        aggressor_convention=AGGRESSOR_CONVENTION,
    )


def first_slice_identity(
    *,
    timeframe: Timeframe,
    replay: bool,
    is_live: bool = False,
    instrument: InstrumentIdentity | None = None,
) -> EvidenceMarketIdentity:
    resolved = instrument or binance_usdm_btcusdt()
    if replay and is_live:
        raise ValueError("Replay evidence cannot also be live.")
    if replay and resolved.venue is not VenueId.BINANCE:
        raise ValueError("Replay fixtures are Binance USD-M evidence only.")
    if resolved.venue is VenueId.OKX:
        source = okx_usdt_swap_source()
        detail = "OKX USDT linear swap public REST (read-only)."
    else:
        source = binance_usdm_source(replay=replay)
        detail = (
            "Replay fixture; not live perpetual evidence."
            if replay
            else "Binance USD-M futures public REST (read-only)."
        )
    provenance = ProviderProvenance(
        provider_name=source.provider_name,
        source_family=source.family,
        adapter_version=source.adapter_version,
        is_live=is_live,
        fallback_used=False,
        is_mock=replay,
        regional_failure=False,
        detail=detail,
    )
    identity = EvidenceMarketIdentity(
        venue=resolved.venue,
        market_type=resolved.market_type,
        instrument=resolved,
        timeframe=timeframe,
        source=source,
        provenance=provenance,
    )
    require_perpetual(identity)
    require_instrument(identity, resolved)
    return identity


class FirstSliceEvaluationClock(CanonicalModel):
    evaluated_at: AwareDatetime
    trigger_interval_start: AwareDatetime
    trigger_interval_end: AwareDatetime


def canonical_first_slice_clock() -> FirstSliceEvaluationClock:
    return FirstSliceEvaluationClock(
        evaluated_at=CANONICAL_EVALUATED_AT,
        trigger_interval_start=CANONICAL_TRIGGER_INTERVAL_START,
        trigger_interval_end=CANONICAL_TRIGGER_INTERVAL_END,
    )
