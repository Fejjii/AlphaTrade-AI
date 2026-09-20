"""Deterministic quote-volume CVD from an ordered perpetual trade stream."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid5

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.coverage import require_complete_window_coverage
from app.market_contracts.cursor import TradeStreamSnapshot, require_contiguous_sequences
from app.market_contracts.enums import (
    DataCompleteness,
    GapState,
    MarketType,
    ReconnectState,
    WarmUpStatus,
)
from app.market_contracts.errors import (
    CursorRecoveryError,
    GapDetectedError,
    IncompleteWarmUpError,
    UnknownAggressorError,
    WrongMarketError,
)
from app.market_contracts.freshness import evaluate_freshness, first_slice_freshness_policy
from app.market_contracts.hashing import semantic_content_hash, with_content_hash
from app.market_contracts.identity import (
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
    coverage_proof_id: UUID
    coverage_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
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


def require_cvd_stream_proof(snapshot: TradeStreamSnapshot) -> None:
    """Derive CVD eligibility from the cursor snapshot. Caller flags are not trusted."""
    cursor = snapshot.cursor
    if cursor.gap_state is not GapState.NONE:
        raise GapDetectedError(
            f"CVD refuses a trade snapshot with gap_state={cursor.gap_state.value}."
        )
    if cursor.warm_up_status is not WarmUpStatus.COMPLETE:
        raise IncompleteWarmUpError(
            "CVD requires complete warm-up proven by the trade-stream cursor."
        )
    if cursor.reconnect_state not in {ReconnectState.CONTINUOUS, ReconnectState.RECOVERED}:
        raise IncompleteWarmUpError(
            f"CVD refuses snapshot reconnect_state={cursor.reconnect_state.value}."
        )
    if not snapshot.trades:
        raise IncompleteWarmUpError("CVD requires a non-empty trade-stream snapshot.")
    if not snapshot.usable:
        raise IncompleteWarmUpError(
            "CVD requires an authoritative complete trade-window coverage proof."
        )
    require_contiguous_sequences([trade.sequence for trade in snapshot.trades])
    terminal = snapshot.trades[-1]
    if cursor.last_sequence != terminal.sequence:
        raise CursorRecoveryError(
            "Cursor last_sequence does not match the snapshot terminal trade."
        )
    require_contiguous_connection(snapshot.trades, cursor.connection_identity)


def build_cvd_window(
    *,
    identity: EvidenceMarketIdentity,
    snapshot: TradeStreamSnapshot,
    window_start: datetime,
    window_end: datetime,
    baseline: Decimal,
    created_at: datetime,
) -> CvdWindow:
    if identity != snapshot.cursor.identity:
        raise WrongMarketError(
            "CVD identity does not exactly match the authoritative trade snapshot identity."
        )
    require_cvd_stream_proof(snapshot)
    require_complete_window_coverage(
        snapshot.coverage,
        identity=identity,
        lineage_id=snapshot.cursor.connection_identity,
        trades=snapshot.trades,
        required_start=window_start,
        required_end=window_end,
    )
    selected = select_trades_in_window(snapshot.trades, start=window_start, end=window_end)
    if not selected:
        raise IncompleteWarmUpError("CVD window contains no trades from the proven snapshot.")
    require_contiguous_sequences([trade.sequence for trade in selected])
    require_contiguous_connection(selected, snapshot.cursor.connection_identity)
    signed, total = accumulate_signed_quote(selected)
    cursor_id = snapshot.cursor.cursor_id
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
        first_trade_id=selected[0].venue_trade_id,
        last_trade_id=selected[-1].venue_trade_id,
        event_set_hash=event_set_hash(selected),
        data_completeness=DataCompleteness.COMPLETE,
        gap_status=GapState.NONE,
        warm_up_complete=True,
        source_connection_id=snapshot.cursor.connection_identity,
        coverage_proof_id=snapshot.coverage.coverage_proof_id,
        coverage_content_hash=snapshot.coverage.content_hash,
        start_cursor_id=cursor_id,
        end_cursor_id=cursor_id,
        aggressor_convention=identity.source.aggressor_convention,
        source_identity=identity.source.adapter_version,
        reset_policy_version=CVD_RESET_POLICY_VERSION,
        arithmetic_policy_version=CVD_ARITHMETIC_POLICY_VERSION,
        event_time_max=selected[-1].event_timestamp,
        receive_time_max=selected[-1].receive_timestamp,
        content_hash="0" * 64,
        created_at=created_at.astimezone(UTC),
    )
    return with_content_hash(window)


def first_slice_cvd_window(
    *,
    identity: EvidenceMarketIdentity,
    series_15m: ClosedOhlcvSeries,
    snapshot: TradeStreamSnapshot,
    created_at: datetime,
    lookback: int = FIRST_SLICE_CVD_LOOKBACK_BARS,
    require_live_freshness: bool = True,
) -> CvdWindow:
    if identity != series_15m.identity:
        raise WrongMarketError(
            "First-slice CVD identity does not exactly match the closed OHLCV identity."
        )
    if series_15m.timeframe is not Timeframe.M15:
        raise ValueError("First-slice CVD is defined on the 15m closed series.")
    if len(series_15m.bars) <= lookback:
        raise IncompleteWarmUpError(
            f"Need more than {lookback} final 15m bars to fix the CVD baseline."
        )
    trigger = series_15m.bars[-1]
    window = build_cvd_window(
        identity=identity,
        snapshot=snapshot,
        window_start=_bar_lookback_start(trigger, lookback),
        window_end=trigger.interval_end,
        baseline=Decimal("0"),
        created_at=created_at,
    )
    terminal_time = window.event_time_max
    if terminal_time is None:
        raise IncompleteWarmUpError("First-slice CVD has no terminal trade evidence.")
    evaluate_freshness(
        source_time=terminal_time,
        evaluated_at=created_at,
        policy=first_slice_freshness_policy(),
        require_fresh=require_live_freshness,
    )
    return window
