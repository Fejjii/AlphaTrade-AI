"""Lesson candidate and accepted lesson schemas (Slice 37)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    LessonCandidateStatus,
    LessonSeverity,
    LessonSourceType,
    ORMModel,
    StrictModel,
)
from app.schemas.structured_rules import StructuredRules


class ProposedRuleUpdate(StrictModel):
    """Optional structured rule change proposed with a lesson."""

    summary: str = Field(max_length=2000)
    structured_rules_patch: StructuredRules | None = None
    create_new_version: bool = False
    attach_to_strategy: bool = False


class LessonCandidateCreate(StrictModel):
    source_type: LessonSourceType = LessonSourceType.JOURNAL
    source_id: UUID | None = None
    related_strategy_id: UUID | None = None
    related_trade_id: UUID | None = None
    related_journal_entry_id: UUID | None = None
    lesson_text: str = Field(min_length=1, max_length=8000)
    mistake_type: str = Field(min_length=1, max_length=60)
    severity: LessonSeverity = LessonSeverity.MEDIUM
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    proposed_rule_update: ProposedRuleUpdate | None = None
    analysis_metadata: dict | None = None


class LessonCandidateAccept(StrictModel):
    reviewer_notes: str | None = Field(default=None, max_length=4000)
    accepted_rule_update: ProposedRuleUpdate | None = None
    attach_rule_to_strategy: bool = False
    create_strategy_version: bool = False
    related_strategy_id: UUID | None = None


class LessonCandidateReject(StrictModel):
    reviewer_notes: str | None = Field(default=None, max_length=4000)


class LessonCandidateArchive(StrictModel):
    reviewer_notes: str | None = Field(default=None, max_length=4000)


class LessonCandidate(ORMModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    source_type: LessonSourceType
    source_id: UUID | None = None
    related_strategy_id: UUID | None = None
    related_trade_id: UUID | None = None
    related_journal_entry_id: UUID | None = None
    lesson_text: str
    mistake_type: str
    severity: LessonSeverity
    confidence: Decimal | None = None
    status: LessonCandidateStatus
    proposed_rule_update: ProposedRuleUpdate | None = None
    accepted_rule_update: ProposedRuleUpdate | None = None
    reviewer_notes: str | None = None
    analysis_metadata: dict | None = None
    created_at: datetime
    reviewed_at: datetime | None = None


class PaginatedLessonCandidates(StrictModel):
    items: list[LessonCandidate]
    total: int
    limit: int
    offset: int


class AcceptedLesson(LessonCandidate):
    """Accepted lesson — searchable trading memory."""

    rag_document_id: UUID | None = None


class PaginatedAcceptedLessons(StrictModel):
    items: list[AcceptedLesson]
    total: int
    limit: int
    offset: int
