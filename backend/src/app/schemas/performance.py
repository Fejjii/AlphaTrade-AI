"""API schemas for performance analytics (Slice 62, portfolio Slice 91A)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analytics import AnalyticsDateRange
from app.schemas.common import StrictModel


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


class PerformanceSnapshotListResponse(BaseModel):
    items: list[PerformanceSnapshotResponse] = Field(default_factory=list)
    total: int = 0


# --- Paper portfolio (Slice 91A) ------------------------------------------- #


class PaperPortfolioSafetyBanner(StrictModel):
    execution_mode: str = "paper"
    paper_only: bool = True
    real_trading_enabled: bool = False
    disclaimer: str = (
        "Paper-only simulated portfolio. Not investment advice. "
        "Does not indicate readiness for real money."
    )


class PaperPortfolioAccount(StrictModel):
    starting_balance: Decimal
    current_equity: Decimal
    cumulative_realized_pnl: Decimal
    unrealized_pnl: Decimal | None = None
    open_trade_count: int = 0
    closed_trade_count: int = 0
    as_of: datetime
    limitations: list[str] = Field(default_factory=list)


class DollarEquityPointSchema(StrictModel):
    index: int
    timestamp: datetime | None = None
    equity: Decimal
    cumulative_realized_pnl: Decimal
    unrealized_pnl: Decimal | None = None
    event: Literal["start", "trade_close", "live"] = "trade_close"


class DailyPortfolioPointSchema(StrictModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    starting_equity: Decimal
    ending_equity: Decimal
    daily_pnl: Decimal
    daily_drawdown: Decimal
    daily_drawdown_pct: float | None = None
    trades_closed: int = 0


class PortfolioTrend(StrictModel):
    label: Literal["improving", "flat", "deteriorating", "insufficient_data"]
    window_days: int = 14
    recent_net_pnl: Decimal | None = None
    prior_net_pnl: Decimal | None = None
    rationale: str = ""


class OpenExposureSummary(StrictModel):
    open_trade_count: int = 0
    proposal_flow_count: int = 0
    paper_validation_count: int = 0
    unrealized_pnl_total: Decimal | None = None
    notional_exposure: Decimal | None = None
    limitations: list[str] = Field(default_factory=list)


class PortfolioFiltersApplied(StrictModel):
    start_date: date | None = None
    end_date: date | None = None
    source: str = "all"
    symbol: str | None = None
    setup: str | None = None
    timeframe: str | None = None
    timezone: str = "UTC"


class PortfolioBreakdowns(StrictModel):
    by_symbol: list[GroupBreakdownSchema] = Field(default_factory=list)
    by_setup: list[GroupBreakdownSchema] = Field(default_factory=list)
    by_timeframe: list[GroupBreakdownSchema] = Field(default_factory=list)
    by_strategy: list[GroupBreakdownSchema] = Field(default_factory=list)
    by_source: list[GroupBreakdownSchema] = Field(default_factory=list)
    by_detector: list[GroupBreakdownSchema] = Field(default_factory=list)


class PaperPortfolioResponse(StrictModel):
    safety: PaperPortfolioSafetyBanner
    account: PaperPortfolioAccount
    metrics: PerformanceMetricsSchema
    open_exposure: OpenExposureSummary
    equity_curve: list[DollarEquityPointSchema] = Field(default_factory=list)
    daily_series: list[DailyPortfolioPointSchema] = Field(default_factory=list)
    breakdowns: PortfolioBreakdowns = Field(default_factory=PortfolioBreakdowns)
    trend: PortfolioTrend
    date_range: AnalyticsDateRange | None = None
    filters_applied: PortfolioFiltersApplied
