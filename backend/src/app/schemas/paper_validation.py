"""Paper validation schemas (Slice 35)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    ORMModel,
    PaperValidationRecommendation,
    PaperValidationStatus,
    StrictModel,
)


class PaperValidationMetrics(StrictModel):
    paper_trades_count: int = Field(ge=0)
    win_rate: float = Field(ge=0, le=1)
    net_pnl: Decimal
    profit_factor: float = Field(ge=0)
    expectancy: Decimal
    max_drawdown_pct: float = Field(ge=0)
    plan_adherence_avg: float | None = None
    early_exit_count: int = Field(default=0, ge=0)
    stop_respected_count: int = Field(default=0, ge=0)


class PaperValidationRun(ORMModel):
    id: UUID
    strategy_id: UUID
    organization_id: UUID
    user_id: UUID
    status: PaperValidationStatus
    paper_eligible: bool
    notes: str | None = None
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
