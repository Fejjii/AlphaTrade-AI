"""Trading analytics API schemas (Slice 31)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import SetupType, StrategyId, StrictModel


class AnalyticsDateRange(StrictModel):
    start: date | None = None
    end: date | None = None


class SetupStatistics(StrictModel):
    setup_type: SetupType
    proposal_count: int = 0
    paper_trade_count: int = 0
    winning_paper_trades: int = 0
    losing_paper_trades: int = 0
    average_paper_pnl: Decimal | None = None
    average_risk_level: str | None = None
    average_confidence: float | None = None
    most_common_mistakes: list[str] = Field(default_factory=list)
    most_common_lessons: list[str] = Field(default_factory=list)
    last_used_at: datetime | None = None


class SetupAnalyticsResponse(StrictModel):
    organization_id: UUID
    user_id: UUID
    setup_type_filter: SetupType | None = None
    date_range: AnalyticsDateRange
    setups: list[SetupStatistics]


class TradeReviewAnalytics(StrictModel):
    total_journaled_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    average_pnl: Decimal | None = None
    most_frequent_setup_type: SetupType | None = None
    most_frequent_mistake_tag: str | None = None
    most_frequent_emotion_tag: str | None = None
    trades_after_daily_loss_warning: int = 0
    trades_after_green_day_warning: int = 0
    trades_blocked_by_risk_engine: int = 0
    proposals_rejected_by_user: int = 0
    proposals_needing_more_analysis: int = 0


class DisciplineScoreResult(StrictModel):
    score: int = Field(ge=0, le=100)
    grade: str
    positive_behaviors: list[str] = Field(default_factory=list)
    negative_behaviors: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)


class RiskBehaviorAnalytics(StrictModel):
    risk_blocks_count: int = 0
    daily_loss_warnings: int = 0
    green_day_warnings: int = 0
    overtrading_warnings: int = 0
    revenge_trading_warnings: int = 0
    proposals_rejected: int = 0
    proposals_needs_more_analysis: int = 0
    paper_orders_rejected: int = 0
    approval_pending_count: int = 0
    approval_approved_count: int = 0
    journal_completion_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    triggered_rules: dict[str, int] = Field(default_factory=dict)


class AnalyticsSummaryToolOutput(StrictModel):
    setup_statistics: list[SetupStatistics]
    discipline_summary: DisciplineScoreResult
    repeated_mistakes: list[str]
    repeated_emotions: list[str]
    improvement_suggestions: list[str]
    trade_review: TradeReviewAnalytics


class AnalyticsSummaryRequest(StrictModel):
    user_id: UUID
    organization_id: UUID
    start_date: date | None = None
    end_date: date | None = None
    setup_type: StrategyId | None = None
