"""Backtest run schemas (Slice 34)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import BacktestRunStatus, ORMModel, StrictModel, Timeframe


class BacktestAssumptions(StrictModel):
    fees_bps: Decimal = Field(default=Decimal("4"), ge=0)
    slippage_bps: Decimal = Field(default=Decimal("5"), ge=0)
    funding_assumption: str = "neutral"
    timeframe: Timeframe = Timeframe.H4
    sample_size: int = Field(default=100, ge=1, le=10000)


class BacktestPlaceholderResult(StrictModel):
    """Deterministic mock result when provider_mode is mock."""

    win_rate: float = Field(ge=0, le=1)
    profit_factor: float = Field(ge=0)
    max_drawdown_pct: float = Field(ge=0)
    trade_count: int = Field(ge=0)
    meets_success_criteria: bool
    note: str = "Placeholder backtest — not a live simulation."


class BacktestRun(ORMModel):
    id: UUID
    strategy_id: UUID
    strategy_version_id: UUID | None = None
    organization_id: UUID
    user_id: UUID
    status: BacktestRunStatus
    assumptions: BacktestAssumptions
    result: BacktestPlaceholderResult | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class BacktestRunCreate(StrictModel):
    assumptions: BacktestAssumptions | None = None


class PaginatedBacktestRuns(StrictModel):
    items: list[BacktestRun]
    total: int
    limit: int
    offset: int
