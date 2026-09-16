"""Versioned Decimal Wilder ATR (Phase 3). Existing float atr_wilder is characterization only."""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum
from itertools import pairwise
from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictModel
from app.schemas.setup_ast import WILDER_ATR_FEATURE_TYPE, WILDER_ATR_FEATURE_VERSION
from app.services.canonical_serialization import canonical_sha256

ARITHMETIC_POLICY_VERSION = "wilder-atr-arithmetic/v1"
FINALITY_POLICY_VERSION = "final-bar/v1"
OUTPUT_SCALE = Decimal("1E-16")
DEFAULT_PERIOD = 14


class OhlcvFinality(StrEnum):
    FINAL = "final"
    FORMING = "forming"


class WilderAtrStatus(StrEnum):
    VALUE = "value"
    MISSING = "missing"


class FinalOhlcvBar(StrictModel):
    revision_id: UUID
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    venue: str = Field(min_length=1, max_length=40)
    market: str = Field(min_length=1, max_length=40)
    instrument: str = Field(min_length=1, max_length=30)
    timeframe: str = Field(min_length=1, max_length=8)
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    finality: OhlcvFinality


class WilderAtrFeatureV1(StrictModel):
    feature_type: str = WILDER_ATR_FEATURE_TYPE
    feature_version: str = WILDER_ATR_FEATURE_VERSION
    venue: str
    market: str
    instrument: str
    timeframe: str
    period: int = DEFAULT_PERIOD
    ordered_final_ohlcv_revision_ids: list[UUID]
    interval_start: datetime | None = None
    interval_end: datetime | None = None
    value: Decimal | None = None
    status: WilderAtrStatus
    missing_reason: str | None = None
    arithmetic_policy_version: str = ARITHMETIC_POLICY_VERSION
    finality_policy_version: str = FINALITY_POLICY_VERSION
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def _quantize_output(value: Decimal) -> Decimal:
    return value.quantize(OUTPUT_SCALE, rounding=ROUND_HALF_EVEN)


def _true_ranges(bars: list[FinalOhlcvBar]) -> list[Decimal]:
    trs: list[Decimal] = []
    for index, bar in enumerate(bars):
        high_low = bar.high - bar.low
        if index == 0:
            trs.append(high_low)
            continue
        prev_close = bars[index - 1].close
        trs.append(
            max(
                high_low,
                abs(bar.high - prev_close),
                abs(bar.low - prev_close),
            )
        )
    return trs


def _identity_ok(bars: list[FinalOhlcvBar]) -> str | None:
    first = bars[0]
    for bar in bars:
        if bar.venue != first.venue or bar.market != first.market:
            return "identity_mismatch"
        if bar.instrument != first.instrument or bar.timeframe != first.timeframe:
            return "identity_mismatch"
        if bar.finality is not OhlcvFinality.FINAL:
            return "forming_candle"
    return None


def _contiguous(bars: list[FinalOhlcvBar]) -> bool:
    for previous, current in pairwise(bars):
        if current.open_time <= previous.open_time:
            return False
        if current.open_time < previous.close_time:
            return False
    return True


def _missing_feature(
    *,
    bars: list[FinalOhlcvBar],
    period: int,
    reason: str,
    venue: str,
    market: str,
    instrument: str,
    timeframe: str,
) -> WilderAtrFeatureV1:
    payload = {
        "feature_type": WILDER_ATR_FEATURE_TYPE,
        "feature_version": WILDER_ATR_FEATURE_VERSION,
        "venue": venue,
        "market": market,
        "instrument": instrument,
        "timeframe": timeframe,
        "period": period,
        "ordered_content_hashes": [bar.content_hash for bar in bars],
        "ordered_revision_ids": [str(bar.revision_id) for bar in bars],
        "status": WilderAtrStatus.MISSING.value,
        "missing_reason": reason,
        "arithmetic_policy_version": ARITHMETIC_POLICY_VERSION,
        "finality_policy_version": FINALITY_POLICY_VERSION,
        "value": None,
    }
    return WilderAtrFeatureV1(
        venue=venue,
        market=market,
        instrument=instrument,
        timeframe=timeframe,
        period=period,
        ordered_final_ohlcv_revision_ids=[bar.revision_id for bar in bars],
        interval_start=bars[0].open_time if bars else None,
        interval_end=bars[-1].close_time if bars else None,
        value=None,
        status=WilderAtrStatus.MISSING,
        missing_reason=reason,
        content_hash=canonical_sha256(payload),
    )


def compute_wilder_atr_v1(
    bars: list[FinalOhlcvBar],
    *,
    period: int = DEFAULT_PERIOD,
    venue: str | None = None,
    market: str | None = None,
    instrument: str | None = None,
    timeframe: str | None = None,
) -> WilderAtrFeatureV1:
    """Compute Wilder ATR from ordered contiguous FINAL candles only.

    Intermediates stay full Decimal precision. Rounding occurs only at the named
    output boundary encoded in ``ARITHMETIC_POLICY_VERSION``.
    """

    identity_venue = venue or (bars[0].venue if bars else "")
    identity_market = market or (bars[0].market if bars else "")
    identity_instrument = instrument or (bars[0].instrument if bars else "")
    identity_timeframe = timeframe or (bars[0].timeframe if bars else "")

    if not bars:
        return _missing_feature(
            bars=[],
            period=period,
            reason="no_bars",
            venue=identity_venue,
            market=identity_market,
            instrument=identity_instrument,
            timeframe=identity_timeframe,
        )
    identity_error = _identity_ok(bars)
    if identity_error is not None:
        return _missing_feature(
            bars=bars,
            period=period,
            reason=identity_error,
            venue=identity_venue,
            market=identity_market,
            instrument=identity_instrument,
            timeframe=identity_timeframe,
        )
    if not _contiguous(bars):
        return _missing_feature(
            bars=bars,
            period=period,
            reason="gap_or_unordered",
            venue=identity_venue,
            market=identity_market,
            instrument=identity_instrument,
            timeframe=identity_timeframe,
        )
    if len(bars) < period:
        return _missing_feature(
            bars=bars,
            period=period,
            reason="warmup_incomplete",
            venue=identity_venue,
            market=identity_market,
            instrument=identity_instrument,
            timeframe=identity_timeframe,
        )

    true_ranges = _true_ranges(bars)
    seed = sum(true_ranges[:period], start=Decimal("0")) / Decimal(period)
    atr = seed
    for true_range in true_ranges[period:]:
        atr = (atr * Decimal(period - 1) + true_range) / Decimal(period)
    output = _quantize_output(atr)
    payload = {
        "feature_type": WILDER_ATR_FEATURE_TYPE,
        "feature_version": WILDER_ATR_FEATURE_VERSION,
        "venue": identity_venue,
        "market": identity_market,
        "instrument": identity_instrument,
        "timeframe": identity_timeframe,
        "period": period,
        "ordered_content_hashes": [bar.content_hash for bar in bars],
        "ordered_revision_ids": [str(bar.revision_id) for bar in bars],
        "interval_start": bars[0].open_time,
        "interval_end": bars[-1].close_time,
        "status": WilderAtrStatus.VALUE.value,
        "value": output,
        "arithmetic_policy_version": ARITHMETIC_POLICY_VERSION,
        "finality_policy_version": FINALITY_POLICY_VERSION,
    }
    return WilderAtrFeatureV1(
        venue=identity_venue,
        market=identity_market,
        instrument=identity_instrument,
        timeframe=identity_timeframe,
        period=period,
        ordered_final_ohlcv_revision_ids=[bar.revision_id for bar in bars],
        interval_start=bars[0].open_time,
        interval_end=bars[-1].close_time,
        value=output,
        status=WilderAtrStatus.VALUE,
        missing_reason=None,
        content_hash=canonical_sha256(payload),
    )
