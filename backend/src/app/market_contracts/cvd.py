"""Deterministic quote-volume CVD from an ordered perpetual trade stream."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid5

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.enums import DataCompleteness, GapState, MarketType, WarmUpStatus
from app.market_contracts.errors import (
    GapDetectedError,
    IncompleteWarmUpError,
    UnknownAggressorError,
)
from app.market_contracts.hashing import semantic_content_hash, with_content_hash
from app.market_contracts.identity import (
    AGGRESSOR_CONVENTION,
    EvidenceMarketIdentity,
    interval_timedelta,
    require_perpetual,
)
from app.market_contracts.models import CanonicalDecimal, CanonicalModel
from app.market_contracts.ohlcv import ClosedOhlcvSeries, OhlcvBar
from app.market_contracts.trades import TradeEvent, order_trades, signed_quote_value
from app.schemas.common import Timeframe

CVD_ARITHMETIC_POLICY_VERSION = "quote-cvd/linear-unrounded/v1"
CVD_RESET_POLICY_VERSION = "reset-at-bar-open/t-minus-32/v1"
FIRST_SLICE_CVD_LOOKBACK_BARS = 32
_CVD_NAMESPACE = UUID("0b91c2e4-7a16-4d3f-8e55-21f0a9c84d77")


class CvdWindow(CanonicalModel):
    cvd_window_id: UUID
    identity: EvidenceMarketIdentity
    window_start: AwareDatetime
    window_end: AwareDatetime
    baseline: CanonicalDecimal
    signed_quote_delta: CanonicalDecimal
    total_quote_volume: CanonicalDecimal
    event_count: int = Field(ge=0)
    first_trade_id: str | None = None
    last_trade_id: str | None = None
    event_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_completeness: DataCompleteness
    gap_status: GapState
    warm_up_complete: bool
    source_connection_id: UUID
    start_cursor_id: UUID
    end_cursor_id: UUID
    aggressor_convention: str = Field(min_length=3, max_length=120)
    source_identity: str = Field(min_length=3, max_length=120)
    reset_policy_version: str = Field(min_length=3, max_length=80)
    arithmetic_policy_version: str = Field(min_length=3, max_length=80)
    event_time_max: AwareDatetime | None = None
    receive_time_max: AwareDatetime | None = None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _window_bounds(self) -> CvdWindow:
        require_perpetual(self.identity)
        if self.window_end <= self.window_start:
            raise ValueError("CVD window must be a half-open interval with end after start.")
        if self.identity.market_type is not MarketType.PERPETUAL:
            raise ValueError("CVD windows are perpetual-only.")
        if self.data_completeness is not DataCompleteness.COMPLETE and self.warm_up_complete:
            raise ValueError("Incomplete windows cannot be marked warm-up complete.")
        return self


def event_set_hash(trades: list[TradeEvent]) -> str:
    return semantic_content_hash({"venue_trade_ids": [trade.venue_trade_id for trade in trades]})


def select_trades_in_window(
    trades: list[TradeEvent],
    *,
    start: datetime,
    end: datetime,
) -> list[TradeEvent]:
    """Inclusive start, exclusive end, then venue sequence order."""
    start_utc = start.astimezone(UTC)
    end_utc = end.astimezone(UTC)
    selected = [trade for trade in trades if start_utc <= trade.event_timestamp < end_utc]
    return order_trades(selected)


def accumulate_signed_quote(trades: list[TradeEvent]) -> tuple[Decimal, Decimal]:
    signed = Decimal("0")
    total = Decimal("0")
    for trade in trades:
        if not trade.aggressor_convention:
            raise UnknownAggressorError("CVD requires a versioned aggressor convention.")
        delta = signed_quote_value(trade)
        signed += delta
        total += trade.quote_quantity
    return signed, total


def cvd_at_close(
    trades: list[TradeEvent],
    *,
    window_start: datetime,
    bar_end: datetime,
    baseline: Decimal,
) -> Decimal:
    selected = select_trades_in_window(trades, start=window_start, end=bar_end)
    signed, _total = accumulate_signed_quote(selected)
    return baseline + signed


def _bar_lookback_start(trigger_bar: OhlcvBar, lookback: int) -> datetime:
    return trigger_bar.interval_start - (interval_timedelta(trigger_bar.timeframe) * lookback)


def first_slice_baseline_open(
    trigger_bar: OhlcvBar, lookback: int = FIRST_SLICE_CVD_LOOKBACK_BARS
) -> datetime:
    if trigger_bar.timeframe is not Timeframe.M15:
        raise ValueError("First-slice CVD baseline is defined on 15m bars.")
    return _bar_lookback_start(trigger_bar, lookback)


def require_contiguous_connection(trades: list[TradeEvent], connection_id: UUID) -> None:
    for trade in trades:
        if trade.source_connection_id != connection_id:
            raise IncompleteWarmUpError("Cross-connection CVD windows are not supported in V1.")


def build_cvd_window(
    *,
    identity: EvidenceMarketIdentity,
    trades: list[TradeEvent],
    window_start: datetime,
    window_end: datetime,
    baseline: Decimal,
    source_connection_id: UUID,
    start_cursor_id: UUID,
    end_cursor_id: UUID,
    gap_status: GapState,
    warm_up_status: WarmUpStatus,
    created_at: datetime,
    aggressor_convention: str = AGGRESSOR_CONVENTION,
) -> CvdWindow:
    if gap_status is not GapState.NONE:
        raise GapDetectedError("Unresolved trade-stream gap makes CVD unusable.")
    if warm_up_status is not WarmUpStatus.COMPLETE:
        raise IncompleteWarmUpError(
            "CVD requires complete warm-up on the current connection epoch."
        )

    selected = select_trades_in_window(trades, start=window_start, end=window_end)
    require_contiguous_connection(selected, source_connection_id)
    signed, total = accumulate_signed_quote(selected)
    event_time_max = selected[-1].event_timestamp if selected else None
    receive_time_max = selected[-1].receive_timestamp if selected else None
    window = CvdWindow(
        cvd_window_id=uuid5(
            _CVD_NAMESPACE,
            f"{identity.instrument.instrument_id}:{window_start.isoformat()}:{window_end.isoformat()}",
        ),
        identity=identity,
        window_start=window_start.astimezone(UTC),
        window_end=window_end.astimezone(UTC),
        baseline=baseline,
        signed_quote_delta=signed,
        total_quote_volume=total,
        event_count=len(selected),
        first_trade_id=selected[0].venue_trade_id if selected else None,
        last_trade_id=selected[-1].venue_trade_id if selected else None,
        event_set_hash=event_set_hash(selected),
        data_completeness=DataCompleteness.COMPLETE,
        gap_status=GapState.NONE,
        warm_up_complete=True,
        source_connection_id=source_connection_id,
        start_cursor_id=start_cursor_id,
        end_cursor_id=end_cursor_id,
        aggressor_convention=aggressor_convention,
        source_identity=identity.source.adapter_version,
        reset_policy_version=CVD_RESET_POLICY_VERSION,
        arithmetic_policy_version=CVD_ARITHMETIC_POLICY_VERSION,
        event_time_max=event_time_max,
        receive_time_max=receive_time_max,
        content_hash="0" * 64,
        created_at=created_at.astimezone(UTC),
    )
    return with_content_hash(window)


def first_slice_cvd_window(
    *,
    identity: EvidenceMarketIdentity,
    series_15m: ClosedOhlcvSeries,
    trades: list[TradeEvent],
    source_connection_id: UUID,
    start_cursor_id: UUID,
    end_cursor_id: UUID,
    created_at: datetime,
    lookback: int = FIRST_SLICE_CVD_LOOKBACK_BARS,
) -> CvdWindow:
    if series_15m.timeframe is not Timeframe.M15:
        raise ValueError("First-slice CVD is defined on the 15m closed series.")
    if len(series_15m.bars) <= lookback:
        raise IncompleteWarmUpError(
            f"Need more than {lookback} final 15m bars to fix the CVD baseline."
        )
    trigger = series_15m.bars[-1]
    window_start = _bar_lookback_start(trigger, lookback)
    window_end = trigger.interval_end
    return build_cvd_window(
        identity=identity,
        trades=trades,
        window_start=window_start,
        window_end=window_end,
        baseline=Decimal("0"),
        source_connection_id=source_connection_id,
        start_cursor_id=start_cursor_id,
        end_cursor_id=end_cursor_id,
        gap_status=GapState.NONE,
        warm_up_status=WarmUpStatus.COMPLETE,
        created_at=created_at,
    )
