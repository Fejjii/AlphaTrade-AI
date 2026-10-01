"""Read-only strategy analytics over canonical records; no persisted aggregates."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import JournalTradeSource, MarketRegime, StrictModel
from app.schemas.journal_statistics import JournalTradeStatsMetrics


class StrategyAnalyticsDimension(StrEnum):
    STRATEGY = "strategy"
    STRATEGY_VERSION = "strategy_version"
    SYMBOL = "symbol"
    TIMEFRAME = "timeframe"
    MARKET_REGIME = "market_regime"
    NESTED_MATURITY_STAGE = "nested_maturity_stage"


class NestedMaturityStage(StrEnum):
    N1 = "N1"
    N2 = "N2"
    N3 = "N3"
    N4_PLUS = "N4_PLUS"


class StrategyAnalyticsFilters(StrictModel):
    """Dates use the journal's effective exit/entry/creation time, inclusively.

    Strategy/version/stage filters apply after the bounded canonical scan, since
    attribution can come from a direct Strategy Brain journal link. Truncation
    therefore also means later matching trades may be absent from the sample.
    """

    source: JournalTradeSource | None = None
    symbol: str | None = Field(default=None, max_length=30)
    timeframe: str | None = Field(default=None, max_length=8)
    market_regime: MarketRegime | None = None
    strategy_id: UUID | None = None
    strategy_version_id: UUID | None = None
    nested_maturity_stage: NestedMaturityStage | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None

    @model_validator(mode="after")
    def valid_dates(self) -> Self:
        dates = [date for date in (self.date_from, self.date_to) if date is not None]
        if any(date.tzinfo is None or date.utcoffset() is None for date in dates):
            raise ValueError("Analytics date filters require timezone-aware timestamps.")
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError("date_from must not be after date_to.")
        return self


class StrategyAnalyticsSample(StrictModel):
    """The actual denominator for one metric; threshold is descriptive only."""

    sample_count: int = Field(ge=0)
    available: bool
    insufficient_history: bool


class StrategyAnalyticsWarning(StrictModel):
    code: Literal[
        "missing_fields",
        "invalid_fields",
        "insufficient_history",
        "costs_unverified",
        "costs_inconsistent",
        "ambiguous_brain_link",
        "conflicting_brain_link",
    ]
    message: str


class StrategyAnalyticsMetrics(JournalTradeStatsMetrics):
    """Existing journal metrics plus coverage and missing foundation metrics.

    Win rate retains journal semantics: wins / (wins + losses), excluding
    breakeven. Expectancy, R and profit factor use recorded net PnL. Costs are
    never deducted again. Drawdown is an absolute peak-to-trough decline of
    cumulative recorded net PnL, starting at zero, over trades with exit times;
    it is not account-equity drawdown. Holding period uses valid entry/exit
    pairs, even when PnL is missing. MAE/MFE are recorded monetary amounts.
    """

    median_r: float | None = None
    maximum_drawdown: Decimal | None = None
    average_holding_period_seconds: float | None = None
    # Subset with all five fields present and gross - fees - funding - slippage == net.
    cost_reconciled_net_pnl_total: Decimal | None = None
    cost_reconciled_expectancy: Decimal | None = None
    cost_complete_sample_count: int = 0
    cost_inconsistent_sample_count: int = 0
    metric_samples: dict[str, StrategyAnalyticsSample] = Field(default_factory=dict)
    missing_fields: dict[str, int] = Field(default_factory=dict)
    invalid_fields: dict[str, int] = Field(default_factory=dict)
    insufficient_history: bool = True
    analytics_warnings: list[StrategyAnalyticsWarning] = Field(default_factory=list)


class StrategyAnalyticsBucket(StrictModel):
    # None is explicitly unassigned; raw dimension values never become sentinel keys.
    dimensions: dict[StrategyAnalyticsDimension, str | None]
    metrics: StrategyAnalyticsMetrics


class StrategyAnalyticsReport(StrictModel):
    contract_version: Literal["strategy-analytics/v1"] = "strategy-analytics/v1"
    organization_id: UUID
    user_id: UUID
    filters: StrategyAnalyticsFilters
    group_by: tuple[StrategyAnalyticsDimension, ...]
    overall: StrategyAnalyticsMetrics
    buckets: list[StrategyAnalyticsBucket]
    total_buckets: int
    limit: int
    offset: int
    scanned_trade_count: int
    truncated: bool
    max_rows: int
    min_sample_size: int
    generated_at: datetime
    outcome_basis: Literal["closed_canonical_journal_trades"] = "closed_canonical_journal_trades"
    stage_basis: Literal["first_recorded_paper_trade_opened_event"] = (
        "first_recorded_paper_trade_opened_event"
    )
    limitations: tuple[str, ...] = (
        "Descriptive recorded history only; sample thresholds do not establish a strategy edge.",
        "Positions and paper trades are not added again to their canonical journal outcomes.",
        "Unknown regime, blank dimensions and absent or ambiguous lineage remain unassigned.",
        "No missing costs, risk, excursions, timestamps or maturity stages are estimated.",
        "Cost reconciliation verifies recorded arithmetic, not execution-cost completeness.",
        "Drawdown covers only recorded net PnL with exit times; partial coverage is explicit.",
        "Strategy/version/stage filters run after the row cap; later matches may be omitted.",
    )
