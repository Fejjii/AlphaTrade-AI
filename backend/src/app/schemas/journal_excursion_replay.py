"""Schemas for deterministic journal trade excursion replay (AT-032).

Record-only. Reads stored HistoricalCandle rows; never triggers live market I/O
or execution. Overwrite of protected (manual/system) excursions requires an
explicit force policy.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.schemas.common import ORMModel, StrictModel
from app.schemas.human_vs_system import RunnerAnalysis


class ExcursionOverwritePolicy(StrEnum):
    """Deterministic policy for persisting replay over existing excursion values."""

    SKIP_PROTECTED = "skip_protected"
    """Write when empty or ``excursion_source=replay``; skip ``manual``/``system``."""

    FORCE = "force"
    """Overwrite any existing source, including manual (explicit opt-in)."""


class JournalExcursionReplayRequest(StrictModel):
    """Request to compute (and optionally persist) replay excursions for one trade."""

    persist: bool = True
    overwrite_policy: ExcursionOverwritePolicy = ExcursionOverwritePolicy.SKIP_PROTECTED
    include_post_exit_runner: bool = True
    exchange: str | None = Field(
        default=None,
        max_length=40,
        description="Override exchange when the trade has none (required for candle lookup).",
    )


class JournalExcursionBatchReplayRequest(StrictModel):
    """Bounded batch replay over eligible closed journal trades."""

    persist: bool = True
    overwrite_policy: ExcursionOverwritePolicy = ExcursionOverwritePolicy.SKIP_PROTECTED
    include_post_exit_runner: bool = False
    exchange: str | None = Field(default=None, max_length=40)
    symbol: str | None = Field(default=None, max_length=30)
    limit: int = Field(default=50, ge=1, le=1000)


class JournalExcursionProvenance(StrictModel):
    """Data-source and freshness provenance for a replay computation."""

    excursion_source: str = "replay"
    data_source: str | None = None
    is_stale: bool = False
    freshness_note: str | None = None
    candle_count: int = 0
    gaps_detected: int = 0
    window_complete: bool = False
    computed_at: datetime | None = None
    limitations: list[str] = Field(default_factory=list)


class JournalExcursionMetrics(StrictModel):
    """Computed excursion metrics (may or may not be persisted)."""

    mfe_price: Decimal | None = None
    mae_price: Decimal | None = None
    mfe_amount: Decimal | None = None
    mae_amount: Decimal | None = None
    available_profit: Decimal | None = None
    realized_vs_available_pct: float | None = None


class JournalTradeExcursionRead(ORMModel):
    """Journal trade projection including excursion provenance (AT-032)."""

    id: UUID
    symbol: str
    exchange: str | None = None
    timeframe: str
    direction: str
    status: str
    entry_price: Decimal | None = None
    entry_time: datetime | None = None
    exit_price: Decimal | None = None
    exit_time: datetime | None = None
    size: Decimal | None = None
    net_pnl: Decimal | None = None
    mfe_price: Decimal | None = None
    mae_price: Decimal | None = None
    mfe_amount: Decimal | None = None
    mae_amount: Decimal | None = None
    available_profit: Decimal | None = None
    realized_vs_available_pct: float | None = None
    excursion_source: str | None = None
    excursion_data_source: str | None = None
    excursion_is_stale: bool | None = None
    excursion_freshness_note: str | None = None
    excursion_candle_count: int | None = None
    excursion_gaps_detected: int | None = None
    excursion_window_complete: bool | None = None
    excursion_computed_at: datetime | None = None


class JournalExcursionReplayResult(StrictModel):
    """Outcome of a single-trade excursion replay."""

    journal_trade_id: UUID
    applied: bool
    skipped_reason: str | None = None
    metrics: JournalExcursionMetrics | None = None
    provenance: JournalExcursionProvenance
    post_exit_runner: RunnerAnalysis | None = None
    trade: JournalTradeExcursionRead | None = None


class JournalExcursionBatchReplayResult(StrictModel):
    """Bounded batch replay summary."""

    processed: int
    applied: int
    skipped: int
    failed: int
    truncated: bool = False
    results: list[JournalExcursionReplayResult]
