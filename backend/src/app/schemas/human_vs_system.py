"""Human versus system comparison schemas (Slice 33)."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictModel, Symbol


class PlanAdherenceBreakdown(StrictModel):
    entry_followed_plan: int = Field(ge=0, le=20)
    size_respected_risk: int = Field(ge=0, le=20)
    stop_loss_respected: int = Field(ge=0, le=20)
    profit_taking_followed: int = Field(ge=0, le=15)
    emotion_controlled: int = Field(ge=0, le=15)
    journal_completed: int = Field(ge=0, le=10)


class HumanVsSystemComparison(StrictModel):
    trade_id: UUID
    symbol: Symbol | None = None
    entry_delta_pct: float | None = None
    exit_vs_system: str | None = None
    size_vs_recommended_pct: float | None = None
    leverage_vs_allowed: str | None = None
    stop_vs_invalidation: str | None = None
    pnl_vs_simulated_placeholder: str | None = None
    emotion_tags: list[str] = Field(default_factory=list)
    emotion_free_baseline: str | None = None
    plan_adherence: PlanAdherenceBreakdown
    plan_adherence_score: int = Field(ge=0, le=100)
    notes: list[str] = Field(default_factory=list)
