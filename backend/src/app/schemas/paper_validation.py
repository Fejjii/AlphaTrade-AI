"""Paper validation schemas (Slice 34)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import ORMModel, PaperValidationStatus, StrictModel


class PaperValidationRun(ORMModel):
    id: UUID
    strategy_id: UUID
    organization_id: UUID
    user_id: UUID
    status: PaperValidationStatus
    paper_eligible: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class PaperValidationSummary(StrictModel):
    strategy_id: UUID
    paper_eligible: bool
    latest_status: PaperValidationStatus | None = None
    runs: list[PaperValidationRun] = Field(default_factory=list)
    total: int = 0
    limitation: str = "Paper validation placeholder — no exchange execution."
