"""Paper eligibility gates and blockers (Slice 38)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import PaperEligibilityStatus, PaperValidationRecommendation, StrictModel
from app.schemas.lesson import AcceptedLesson, LessonCandidate


class LessonSourceMetadata(StrictModel):
    """Provenance when a strategy version is created from an accepted lesson."""

    lesson_id: UUID
    mistake_type: str
    accepted_lesson_text: str
    rule_update_summary: str | None = None
    reviewer_notes: str | None = None
    created_at: datetime


class BacktestMetricsSummary(StrictModel):
    trade_count: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: Decimal = Decimal("0")
    max_drawdown_pct: float = 0.0
    recommendation: str | None = None


class PaperEligibilityReport(StrictModel):
    strategy_id: UUID
    status: PaperEligibilityStatus
    paper_eligible: bool
    testability_score: int
    blockers: list[str] = Field(default_factory=list)
    eligibility_reasons: list[str] = Field(default_factory=list)
    latest_backtest: BacktestMetricsSummary | None = None
    accepted_lessons: list[AcceptedLesson] = Field(default_factory=list)
    unresolved_lesson_candidates: list[LessonCandidate] = Field(default_factory=list)
    paper_validation_recommendation: PaperValidationRecommendation | None = None
    recommendation: str = Field(
        description="continue | improve | restrict | retire — paper validation guidance only."
    )
    real_trading_enabled: bool = False
    limitations: list[str] = Field(default_factory=list)
