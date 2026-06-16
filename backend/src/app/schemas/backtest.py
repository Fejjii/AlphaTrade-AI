"""Backtest schemas (Slice 35 — deterministic engine v1)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    BacktestRecommendation,
    BacktestRunStatus,
    ORMModel,
    StrictModel,
    Timeframe,
    TradeDirection,
)


class BacktestAssumptions(StrictModel):
    symbol: str = Field(default="BTCUSDT", min_length=2, max_length=30)
    exchange: str = Field(default="binance", min_length=1, max_length=40)
    timeframe: Timeframe = Timeframe.H4
    start_date: date | None = None
    end_date: date | None = None
    initial_capital: Decimal = Field(default=Decimal("10000"), gt=0)
    fees_bps: Decimal = Field(default=Decimal("4"), ge=0)
    slippage_bps: Decimal = Field(default=Decimal("5"), ge=0)
    funding_assumption: str = "neutral"
    risk_per_trade_pct: Decimal = Field(default=Decimal("1"), gt=0, le=Decimal("5"))
    max_trades: int | None = Field(default=None, ge=1, le=10000)
    sample_size: int = Field(default=500, ge=50, le=10000)


class BacktestTradeRecord(StrictModel):
    id: UUID | None = None
    entry_time: datetime
    exit_time: datetime
    direction: TradeDirection
    entry_price: Decimal
    exit_price: Decimal
    stop_loss: Decimal
    size: Decimal
    fees: Decimal
    slippage_cost: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    tp_hit_status: str
    exit_reason: str
    rule_notes: str | None = None


class EquityCurvePoint(StrictModel):
    timestamp: datetime
    equity: Decimal


class BacktestMetrics(StrictModel):
    trade_count: int = Field(ge=0)
    win_rate: float = Field(ge=0, le=1)
    profit_factor: float = Field(ge=0)
    expectancy: Decimal
    max_drawdown_pct: float = Field(ge=0)
    average_win: Decimal
    average_loss: Decimal
    largest_win: Decimal
    largest_loss: Decimal
    consecutive_losses: int = Field(ge=0)
    average_time_in_trade_bars: float = Field(ge=0)
    total_fees: Decimal
    total_slippage: Decimal
    net_pnl: Decimal
    return_pct: float
    ending_equity: Decimal
    equity_curve: list[EquityCurvePoint] = Field(default_factory=list)
    symbol: str
    timeframe: str


class BacktestResult(StrictModel):
    """Deterministic backtest output — historical simulation only."""

    metrics: BacktestMetrics
    trades: list[BacktestTradeRecord] = Field(default_factory=list)
    recommendation: BacktestRecommendation
    meets_success_criteria: bool = False
    limitations: list[str] = Field(default_factory=list)
    data_quality: str = "ok"
    note: str = (
        "Historical simulation only — not a guarantee of future performance. "
        "Real trading remains disabled."
    )


# Backward-compatible alias for older tests/docs
BacktestPlaceholderResult = BacktestResult


class BacktestRun(ORMModel):
    id: UUID
    strategy_id: UUID
    strategy_version_id: UUID | None = None
    organization_id: UUID
    user_id: UUID
    status: BacktestRunStatus
    assumptions: BacktestAssumptions
    result: BacktestResult | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class BacktestRunCreate(StrictModel):
    assumptions: BacktestAssumptions | None = None
    strategy_version_id: UUID | None = None


class PaginatedBacktestRuns(StrictModel):
    items: list[BacktestRun]
    total: int
    limit: int
    offset: int


class PaginatedBacktestTrades(StrictModel):
    items: list[BacktestTradeRecord]
    total: int
    limit: int
    offset: int
