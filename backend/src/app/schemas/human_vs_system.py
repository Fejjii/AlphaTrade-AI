"""Human versus system comparison schemas (Slice 33-36)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import AnalysisConfidence, StrictModel, Symbol


class PlanAdherenceBreakdown(StrictModel):
    entry_followed_plan: int = Field(ge=0, le=20)
    size_respected_risk: int = Field(ge=0, le=20)
    stop_loss_respected: int = Field(ge=0, le=20)
    profit_taking_followed: int = Field(ge=0, le=15)
    emotion_controlled: int = Field(ge=0, le=15)
    journal_completed: int = Field(ge=0, le=10)


class RunnerAnalysis(StrictModel):
    early_exit_flag: bool | None = None
    missed_profit_estimate: Decimal | None = None
    max_favorable_excursion_after_exit: Decimal | None = None
    max_adverse_excursion_after_exit: Decimal | None = None
    would_runner_have_helped: bool | None = None
    tp2_would_have_hit: bool | None = None
    tp3_would_have_hit: bool | None = None
    runner_invalidation_would_have_hit: bool | None = None
    recommended_lesson: str | None = None
    confidence: AnalysisConfidence = AnalysisConfidence.LOW
    limitations: list[str] = Field(default_factory=list)


class StopLossAnalysis(StrictModel):
    stop_violation_flag: bool | None = None
    planned_loss: Decimal | None = None
    actual_loss: Decimal | None = None
    avoidable_loss_estimate: Decimal | None = None
    lesson: str | None = None
    future_restriction_suggestion: str | None = None
    limitations: list[str] = Field(default_factory=list)


class HumanVsSystemComparison(StrictModel):
    trade_id: UUID
    symbol: Symbol | None = None
    entry_quality_delta_pct: float | None = None
    exit_quality_delta: str | None = None
    size_discipline_delta_pct: float | None = None
    leverage_discipline_delta: str | None = None
    stop_loss_discipline_delta: str | None = None
    planned_loss_vs_actual: str | None = None
    early_exit_flag: bool | None = None
    missed_runner: RunnerAnalysis | None = None
    emotional_mistake_classification: list[str] = Field(default_factory=list)
    rule_violation_cost_estimate: Decimal | None = None
    plan_adherence: PlanAdherenceBreakdown
    plan_adherence_score: int = Field(ge=0, le=100)
    system_would_have_done: str | None = None
    backtest_context: str | None = None
    # Slice 34 backward-compatible aliases
    entry_delta_pct: float | None = None
    exit_delta: str | None = None
    exit_vs_system: str | None = None
    size_delta_pct: float | None = None
    size_vs_recommended_pct: float | None = None
    leverage_delta: str | None = None
    leverage_vs_allowed: str | None = None
    stop_behavior_delta: str | None = None
    stop_vs_invalidation: str | None = None
    missed_runner_profit_placeholder: str | None = None
    pnl_vs_simulated_placeholder: str | None = None
    stop_loss_analysis: StopLossAnalysis | None = None
    emotion_tags: list[str] = Field(default_factory=list)
    emotion_free_baseline: str | None = None
    notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DisciplineAnalysis(StrictModel):
    """Journal-focused discipline breakdown (Slice 36)."""

    journal_entry_id: UUID
    comparison: HumanVsSystemComparison
    lessons_generated: list[str] = Field(default_factory=list)
    lesson_candidate_ids: list[UUID] = Field(default_factory=list)
