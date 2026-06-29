"""Paper validation session result schemas (Slice 83 — outcome classification, record only)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    PaperValidationCriteriaMet,
    PaperValidationDisciplineAssessment,
    PaperValidationEntryAssessment,
    PaperValidationOutcome,
    StrictModel,
)

RECORD_PAPER_VALIDATION_OUTCOME_CONFIRM = "RECORD_PAPER_VALIDATION_OUTCOME"
_MAX_NOTES = 2000


class PaperValidationSessionResultItem(StrictModel):
    result_id: UUID
    run_session_id: UUID
    run_plan_id: UUID
    outcome: PaperValidationOutcome
    success_criteria_met: PaperValidationCriteriaMet
    success_criteria_notes: str | None = None
    failure_criteria_met: PaperValidationCriteriaMet
    failure_criteria_notes: str | None = None
    invalidation_hit: bool
    invalidation_notes: str | None = None
    entry_assessment: PaperValidationEntryAssessment
    discipline_assessment: PaperValidationDisciplineAssessment
    behaved_as_expected: bool | None = None
    lessons: str | None = None
    recorded_at: datetime
    created_at: datetime


class PaperValidationSessionResultCreateRequest(StrictModel):
    confirm: str
    outcome: PaperValidationOutcome
    success_criteria_met: PaperValidationCriteriaMet
    success_criteria_notes: str | None = Field(default=None, max_length=_MAX_NOTES)
    failure_criteria_met: PaperValidationCriteriaMet
    failure_criteria_notes: str | None = Field(default=None, max_length=_MAX_NOTES)
    invalidation_hit: bool = False
    invalidation_notes: str | None = Field(default=None, max_length=_MAX_NOTES)
    entry_assessment: PaperValidationEntryAssessment
    discipline_assessment: PaperValidationDisciplineAssessment
    behaved_as_expected: bool | None = None
    lessons: str | None = Field(default=None, max_length=_MAX_NOTES)


class PaperValidationSessionResultUpdateRequest(StrictModel):
    outcome: PaperValidationOutcome | None = None
    success_criteria_met: PaperValidationCriteriaMet | None = None
    success_criteria_notes: str | None = Field(default=None, max_length=_MAX_NOTES)
    failure_criteria_met: PaperValidationCriteriaMet | None = None
    failure_criteria_notes: str | None = Field(default=None, max_length=_MAX_NOTES)
    invalidation_hit: bool | None = None
    invalidation_notes: str | None = Field(default=None, max_length=_MAX_NOTES)
    entry_assessment: PaperValidationEntryAssessment | None = None
    discipline_assessment: PaperValidationDisciplineAssessment | None = None
    behaved_as_expected: bool | None = None
    lessons: str | None = Field(default=None, max_length=_MAX_NOTES)


class PaperValidationSessionResultCreateResult(StrictModel):
    result: PaperValidationSessionResultItem
    already_exists: bool = False
