"""Backtest schemas (Slice 35 / AT-034 — deterministic engine v2).

Backward compatible: every new field is optional or defaulted so previously
stored assumptions/result JSON still validates.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    BacktestRecommendation,
    BacktestRunStatus,
    BacktestSplitLabel,
    ORMModel,
    StrictModel,
    Timeframe,
    TradeDirection,
)


class BacktestSplitMode(StrEnum):
    """Walk-forward / holdout split mode (AT-034)."""

    NONE = "none"
    HOLDOUT = "holdout"
    ROLLING = "rolling"


class BacktestSplitConfig(StrictModel):
    """Optional walk-forward configuration for engine v2."""

    mode: BacktestSplitMode = BacktestSplitMode.NONE
    oos_fraction: float = Field(default=0.3, gt=0, lt=1)
    window_bars: int | None = Field(default=None, ge=100)
    step_bars: int | None = Field(default=None, ge=50)


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
    funding_rate_bps_per_8h: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("-500"),
        le=Decimal("500"),
    )
    runner_trail_pct: Decimal = Field(default=Decimal("1.5"), gt=0, le=Decimal("20"))
    split_config: BacktestSplitConfig | None = None
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
    mfe_price: Decimal | None = None
    mae_price: Decimal | None = None
    mfe_amount: Decimal | None = None
    mae_amount: Decimal | None = None
    available_profit: Decimal | None = None
    capture_pct: Decimal | None = None
    funding_cost: Decimal = Decimal("0")
    split_label: BacktestSplitLabel = BacktestSplitLabel.IN_SAMPLE
    split_index: int = 0
    sequence: int | None = None


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
    total_funding: Decimal = Decimal("0")
    net_pnl: Decimal
    return_pct: float
    ending_equity: Decimal
    equity_curve: list[EquityCurvePoint] = Field(default_factory=list)
    symbol: str
    timeframe: str


class BacktestSplitMetrics(StrictModel):
    """Compact per-split metrics subset (AT-034 walk-forward)."""

    split_label: BacktestSplitLabel
    split_index: int
    start_time: datetime
    end_time: datetime
    trade_count: int = Field(ge=0)
    win_rate: float = Field(ge=0, le=1)
    profit_factor: float = Field(ge=0)
    expectancy: Decimal
    net_pnl: Decimal
    max_drawdown_pct: float = Field(ge=0)


class BacktestDatasetSummary(StrictModel):
    """Immutable dataset snapshot summary attached to a result."""

    dataset_hash: str
    candle_count: int
    gap_count: int
    stale_count: int
    first_open_time: datetime | None = None
    last_open_time: datetime | None = None
    source_counts: dict[str, int] = Field(default_factory=dict)


class BacktestResult(StrictModel):
    """Deterministic backtest output — historical simulation only."""

    metrics: BacktestMetrics
    trades: list[BacktestTradeRecord] = Field(default_factory=list)
    recommendation: BacktestRecommendation
    meets_success_criteria: bool = False
    limitations: list[str] = Field(default_factory=list)
    data_quality: str = "ok"
    rule_engine_source: str = "unsupported"
    note: str = (
        "Historical simulation only — not a guarantee of future performance. "
        "Real trading remains disabled."
    )
    result_hash: str | None = None
    engine_version: str | None = None
    split_metrics: list[BacktestSplitMetrics] | None = None
    oos_metrics: BacktestSplitMetrics | None = None
    dataset_summary: BacktestDatasetSummary | None = None
    cancelled: bool = False
    processed_bars: int | None = None
    total_bars: int | None = None


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
