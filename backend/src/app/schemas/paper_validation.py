"""Paper validation schemas (Slice 35, 39)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    ORMModel,
    PaperSignalStatus,
    PaperTradeStatus,
    PaperValidationRecommendation,
    PaperValidationRuntimeMode,
    PaperValidationStatus,
    StrictModel,
    TradeDirection,
)


class PaperValidationConfig(StrictModel):
    symbol: str = "BTCUSDT"
    exchange: str = "mock"
    timeframe: str = "15m"
    initial_capital: Decimal = Decimal("10000")
    fees_bps: Decimal = Decimal("10")
    slippage_bps: Decimal = Decimal("5")
    risk_per_trade_pct: Decimal = Decimal("1")
    max_open_trades: int = Field(default=3, ge=1, le=20)
    trade_timeout_bars: int = Field(default=48, ge=1, le=500)


class PaperValidationMetrics(StrictModel):
    paper_trades_count: int = Field(ge=0)
    win_rate: float = Field(ge=0, le=1)
    net_pnl: Decimal
    gross_pnl: Decimal = Decimal("0")
    profit_factor: float = Field(ge=0)
    expectancy: Decimal
    max_drawdown_pct: float = Field(ge=0)
    total_fees: Decimal = Decimal("0")
    total_slippage: Decimal = Decimal("0")
    average_win: Decimal = Decimal("0")
    average_loss: Decimal = Decimal("0")
    consecutive_losses: int = Field(default=0, ge=0)
    average_holding_time_hours: float = Field(default=0.0, ge=0)
    plan_adherence_avg: float | None = None
    early_exit_count: int = Field(default=0, ge=0)
    stop_respected_count: int = Field(default=0, ge=0)
    runner_helped_count: int = Field(default=0, ge=0)


class PaperValidationRunStart(StrictModel):
    runtime_mode: PaperValidationRuntimeMode = PaperValidationRuntimeMode.SCAN_ONLY
    config: PaperValidationConfig | None = None


class PaperValidationRun(ORMModel):
    id: UUID
    strategy_id: UUID
    strategy_version_id: UUID | None = None
    organization_id: UUID
    user_id: UUID
    status: PaperValidationStatus
    runtime_mode: PaperValidationRuntimeMode = PaperValidationRuntimeMode.SCAN_ONLY
    paper_eligible: bool
    notes: str | None = None
    config: PaperValidationConfig | None = None
    blockers: list[str] = Field(default_factory=list)
    last_scan_at: datetime | None = None
    last_tick_at: datetime | None = None
    last_scan_result: dict | None = None
    ended_at: datetime | None = None
    metrics: PaperValidationMetrics | None = None
    recommendation: PaperValidationRecommendation | None = None
    created_at: datetime
    updated_at: datetime


class PaperValidationSummary(StrictModel):
    strategy_id: UUID
    paper_eligible: bool
    latest_status: PaperValidationStatus | None = None
    runs: list[PaperValidationRun]
    total: int
    limitation: str = "Paper validation tracks simulated paper trades only — no exchange execution."


class PaperSignalResult(StrictModel):
    id: UUID
    paper_validation_run_id: UUID
    strategy_id: UUID
    triggered: bool
    status: PaperSignalStatus
    symbol: str
    exchange: str
    timeframe: str
    direction: TradeDirection
    matched_entry_blocks: list[str] = Field(default_factory=list)
    blocked_no_trade_filters: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    suggested_entry: Decimal | None = None
    stop_loss: Decimal | None = None
    invalidation: str | None = None
    tp_plan: dict | None = None
    runner_plan: dict | None = None
    reason: str | None = None
    limitations: list[str] = Field(default_factory=list)
    rule_engine_source: str | None = None
    created_at: datetime


class PaperTradeRecord(ORMModel):
    id: UUID
    paper_validation_run_id: UUID
    strategy_id: UUID
    strategy_version_id: UUID | None = None
    created_from_signal_id: UUID | None = None
    symbol: str
    exchange: str
    timeframe: str
    direction: TradeDirection
    entry_price: Decimal | None = None
    entry_time: datetime | None = None
    size: Decimal | None = None
    stop_loss: Decimal | None = None
    invalidation: str | None = None
    tp_plan: dict | None = None
    runner_plan: dict | None = None
    status: PaperTradeStatus
    exit_price: Decimal | None = None
    exit_time: datetime | None = None
    exit_reason: str | None = None
    gross_pnl: Decimal | None = None
    net_pnl: Decimal | None = None
    fees: Decimal | None = None
    slippage: Decimal | None = None
    rule_engine_source: str | None = None
    created_at: datetime
    updated_at: datetime


class PaperPosition(PaperTradeRecord):
    """Open paper trade exposed as a position."""


class PaperScanResult(StrictModel):
    run_id: UUID
    signal: PaperSignalResult | None = None
    trade_created: bool = False
    blockers: list[str] = Field(default_factory=list)
    scanned_at: datetime


class PaperTickResult(StrictModel):
    run_id: UUID
    trades_closed: int = 0
    trades_open: int = 0
    metrics: PaperValidationMetrics | None = None
    recommendation: PaperValidationRecommendation | None = None
    ticked_at: datetime


class PaginatedPaperSignals(StrictModel):
    items: list[PaperSignalResult]
    total: int
    limit: int
    offset: int


class PaginatedPaperTrades(StrictModel):
    items: list[PaperTradeRecord]
    total: int
    limit: int
    offset: int


class PaginatedPaperPositions(StrictModel):
    items: list[PaperPosition]
    total: int
