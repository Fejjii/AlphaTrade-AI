"""API schemas for performance analytics (Slice 62)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class EquityPointSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    index: int
    timestamp: datetime | None = None
    cumulative_pnl: Decimal


class PerformanceMetricsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trade_count: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    net_pnl: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    total_fees: Decimal
    total_funding: Decimal
    avg_win: Decimal
    avg_loss: Decimal
    expectancy: Decimal
    profit_factor: float | None = None
    avg_r_multiple: float | None = None
    max_drawdown: Decimal
    max_drawdown_pct: float | None = None
    avg_duration_seconds: float | None = None
    violations: int
    equity_curve: list[EquityPointSchema] = Field(default_factory=list)


class GroupBreakdownSchema(BaseModel):
    key: str
    metrics: PerformanceMetricsSchema


class PerformanceReport(BaseModel):
    """Account-level performance plus grouped breakdowns."""

    account: PerformanceMetricsSchema
    by_strategy: list[GroupBreakdownSchema] = Field(default_factory=list)
    by_symbol: list[GroupBreakdownSchema] = Field(default_factory=list)
    by_timeframe: list[GroupBreakdownSchema] = Field(default_factory=list)
    by_source: list[GroupBreakdownSchema] = Field(default_factory=list)


class PerformanceSnapshotResponse(BaseModel):
    """Lightweight view of a persisted account snapshot."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope: str
    as_of: datetime
    trade_count: int
    net_pnl: Decimal
    win_rate: float
    profit_factor: float | None = None
    max_drawdown: Decimal
    max_drawdown_pct: float | None = None
