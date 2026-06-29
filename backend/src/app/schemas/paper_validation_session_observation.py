"""Paper validation session observation schemas (Slice 83 — manual log, record only)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import PaperValidationObservationKind, StrictModel

RECORD_PAPER_VALIDATION_OBSERVATION_CONFIRM = "RECORD_PAPER_VALIDATION_OBSERVATION"
_MAX_NOTE = 1000


class PaperValidationSessionObservationItem(StrictModel):
    observation_id: UUID
    run_session_id: UUID
    run_plan_id: UUID
    observation_kind: PaperValidationObservationKind
    observed_price: float | None = None
    observed_at: datetime | None = None
    note: str | None = None
    created_at: datetime


class PaginatedPaperValidationSessionObservations(StrictModel):
    items: list[PaperValidationSessionObservationItem]
    total: int
    limit: int
    offset: int


class PaperValidationSessionObservationCreateRequest(StrictModel):
    confirm: str
    observation_kind: PaperValidationObservationKind
    observed_price: float | None = None
    observed_at: datetime | None = None
    note: str | None = Field(default=None, max_length=_MAX_NOTE)
