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
    JournalEntryMethod,
    JournalTradeSource,
    MarketRegime,
    ORMModel,
    StrictModel,
    Timeframe,
    TradeDirection,
)
from app.schemas.journal_statistics import (
    ExecutionActor,
    JournalStatsWarning,
    JournalTradeStatsMetrics,
    SampleConfidence,
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
    config_hash: str | None = None
    dataset_id: UUID | None = None
    engine_version: str | None = None
    result_hash: str | None = None
    idempotency_key: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    processed_bars: int | None = None
    total_bars: int | None = None
    created_at: datetime
    updated_at: datetime


class BacktestRunCreate(StrictModel):
    assumptions: BacktestAssumptions | None = None
    strategy_version_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)


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


class BacktestVerifyResult(StrictModel):
    """Deterministic re-execution check against a frozen config + dataset."""

    run_id: UUID
    result_hash_stored: str | None = None
    result_hash_recomputed: str | None = None
    match: bool
    dataset_ok: bool
    detail: str | None = None


class BacktestJournalMode(StrEnum):
    DRY_RUN = "dry_run"
    COMMIT = "commit"


class BacktestJournalRowOutcome(StrEnum):
    CREATED = "created"
    WOULD_CREATE = "would_create"
    DUPLICATE = "duplicate"
    INVALID = "invalid"


class BacktestJournalRequest(StrictModel):
    dry_run: bool = True


class BacktestJournalRowResult(StrictModel):
    index: int
    backtest_trade_id: UUID | None = None
    outcome: BacktestJournalRowOutcome
    external_ref: str | None = None
    journal_trade_id: UUID | None = None
    errors: list[str] = Field(default_factory=list)


class BacktestJournalResult(StrictModel):
    run_id: UUID
    dry_run: bool
    committed: bool
    total_rows: int
    created_count: int
    duplicate_count: int
    invalid_count: int
    results: list[BacktestJournalRowResult] = Field(default_factory=list)


class JournalComparisonCohort(StrEnum):
    HUMAN = "human"
    PAPER_SYSTEM = "paper_system"
    BACKTEST = "backtest"


class ComparisonBreakdownDimension(StrEnum):
    """Breakdown dimensions for AT-036 journal comparison."""

    SETUP = "setup"
    MARKET_REGIME = "market_regime"


class JournalComparisonFilters(StrictModel):
    strategy_id: UUID | None = None
    strategy_version_id: UUID | None = None
    setup_id: UUID | None = None
    symbol: str | None = Field(default=None, max_length=30)
    timeframe: str | None = Field(default=None, max_length=8)
    date_from: datetime | None = None
    date_to: datetime | None = None
    market_regime: MarketRegime | None = None
    entry_method: JournalEntryMethod | None = None
    source: JournalTradeSource | None = None


class JournalComparisonCohortResult(StrictModel):
    cohort: JournalComparisonCohort
    metrics: JournalTradeStatsMetrics
    sample_count: int = Field(ge=0)
    truncated: bool = False


class DecisionQualityMetrics(StrictModel):
    """Record-only entry timing, early-exit, and missed-profit aggregates (AT-036)."""

    timing_sample_count: int = 0
    average_entry_timing_pct: float | None = None
    early_exit_sample_count: int = 0
    early_exit_count: int | None = None
    early_exit_rate: float | None = None
    missed_profit_sample_count: int = 0
    average_missed_profit: Decimal | None = None
    average_capture_pct: float | None = None
    warnings: list[JournalStatsWarning] = Field(default_factory=list)


class ComparisonScorecard(StrictModel):
    actor: ExecutionActor
    metrics: JournalTradeStatsMetrics
    decision_quality: DecisionQualityMetrics
    sample_count: int = Field(ge=0)
    truncated: bool = False


class ComparisonDimensionBucket(StrictModel):
    key: str
    group_id: UUID | None = None
    label: str
    metrics: JournalTradeStatsMetrics
    sample_count: int = Field(ge=0)


class ComparisonBreakdown(StrictModel):
    dimension: ComparisonBreakdownDimension
    buckets: list[ComparisonDimensionBucket]


class ComparisonLinks(StrictModel):
    """Frontend paths (not API URLs) for related journal / research surfaces."""

    journal_trades_path: str = "/journal"
    journal_statistics_path: str = "/journal/statistics"
    journal_comparison_path: str = "/journal/comparison"
    backtests_path: str = "/backtests"
    research_validation_path: str = "/research-validation"
    paper_validation_candidates_path: str = "/paper-validation/candidates"


class JournalComparisonResponse(StrictModel):
    filters: JournalComparisonFilters
    cohorts: list[JournalComparisonCohortResult]
    scorecards: list[ComparisonScorecard] = Field(default_factory=list)
    by_entry_method: list[ComparisonDimensionBucket] = Field(default_factory=list)
    by_source: list[ComparisonDimensionBucket] = Field(default_factory=list)
    rule_compliance: list[ComparisonDimensionBucket] = Field(default_factory=list)
    decision_quality: DecisionQualityMetrics = Field(default_factory=DecisionQualityMetrics)
    breakdowns: list[ComparisonBreakdown] = Field(default_factory=list)
    links: ComparisonLinks = Field(default_factory=ComparisonLinks)
    confidence: SampleConfidence = SampleConfidence.INSUFFICIENT
    warnings: list[JournalStatsWarning] = Field(default_factory=list)
    max_rows: int
    generated_at: datetime
    note: str = (
        "Record-only human-vs-system performance and decision-quality comparison "
        "(AT-036) over canonical journal trades. Advisory only — never feeds "
        "execution or risk decisions."
    )


class SetupEvidenceTier(StrEnum):
    TIER1 = "tier1"
    TIER2 = "tier2"
    TIER3 = "tier3"


class SetupEvidenceThresholds(StrictModel):
    tier1_oos_min_trades: int
    tier1_oos_min_profit_factor: float
    tier1_min_confirm_trades: int
    tier2_min_trades: int
    tier2_oos_min_trades: int
    tier2_oos_min_profit_factor: float


class SetupEvidenceMeasured(StrictModel):
    oos_trade_count: int = 0
    oos_profit_factor: float | None = None
    oos_expectancy: Decimal | None = None
    confirm_trade_count: int = 0
    confirm_expectancy: Decimal | None = None
    total_backtest_trades: int = 0
    backtest_run_id: UUID | None = None


class SetupEvidenceItem(StrictModel):
    strategy_id: UUID
    strategy_version_id: UUID
    strategy_name: str
    version: int
    tier: SetupEvidenceTier
    measured: SetupEvidenceMeasured
    thresholds: SetupEvidenceThresholds
    note: str = "Advisory only — never feeds execution or risk decisions."


class SetupEvidenceResponse(StrictModel):
    items: list[SetupEvidenceItem]
    generated_at: datetime
    note: str = "Advisory only — never feeds execution or risk decisions."
