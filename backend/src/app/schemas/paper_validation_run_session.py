"""Paper validation run session schemas (Slice 82 — manual start, record only, no engine)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    PaperValidationDraftRiskMode,
    PaperValidationRunSessionStatus,
    StrictModel,
)

START_PAPER_VALIDATION_RUN_CONFIRM = "START_PAPER_VALIDATION_RUN"
_MAX_NOTES = 1000


class PaperValidationRunSessionItem(StrictModel):
    session_id: UUID
    run_plan_id: UUID
    candidate_id: UUID
    draft_id: UUID
    source_alert_id: UUID
    symbol: str | None = None
    timeframe: str | None = None
    condition: str | None = None
    direction: str | None = None
    risk_mode: PaperValidationDraftRiskMode
    validation_window: str | None = None
    observation_timeframe: str | None = None
    max_duration_minutes: int | None = None
    session_status: PaperValidationRunSessionStatus
    notes: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime


class PaginatedPaperValidationRunSessions(StrictModel):
    items: list[PaperValidationRunSessionItem]
    total: int
    limit: int
    offset: int


class PaperValidationRunSessionStartRequest(StrictModel):
    confirm: str
    notes: str | None = Field(default=None, max_length=_MAX_NOTES)


class PaperValidationRunSessionStartResult(StrictModel):
    session: PaperValidationRunSessionItem
    already_active: bool = False


class PaperValidationRunSessionStatusUpdate(StrictModel):
    # Allowed transition targets are enforced in the service layer so an invalid
    # (but enum-valid) value such as ``running`` returns a clean 422 instead of a
    # field-validator ValueError that the error handler cannot serialize.
    session_status: PaperValidationRunSessionStatus
