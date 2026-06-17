"""Trade journal API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.auth import TenantDep
from app.core.dependencies import (
    HumanVsSystemServiceDep,
    JournalServiceDep,
    LessonCandidateServiceDep,
    SessionDep,
)
from app.schemas.human_vs_system import DisciplineAnalysis
from app.schemas.journal import (
    JournalEntry,
    JournalEntryCreate,
    JournalEntryPrefill,
    JournalEntryUpdate,
    PaginatedJournalEntries,
)
from app.schemas.lesson import LessonCandidate
from app.security.rbac import TraderDep
from app.security.tenant import ensure_same_organization

router = APIRouter(prefix="/journal", tags=["journal"])


@router.post("/entries", response_model=JournalEntry, summary="Create journal entry")
async def create_journal_entry(
    body: JournalEntryCreate,
    tenant: TraderDep,
    journal_service: JournalServiceDep,
    session: SessionDep,
) -> JournalEntry:
    payload = body.model_copy(
        update={"organization_id": tenant.organization_id, "user_id": tenant.user_id}
    )
    result = journal_service.create(payload)
    session.commit()
    return result


@router.get(
    "/prefill",
    response_model=JournalEntryPrefill,
    summary="Prefill journal from proposal or position",
)
async def prefill_journal_entry(
    tenant: TenantDep,
    journal_service: JournalServiceDep,
    linked_proposal_id: uuid.UUID | None = Query(default=None),
    linked_position_id: uuid.UUID | None = Query(default=None),
) -> JournalEntryPrefill:
    if linked_proposal_id is None and linked_position_id is None:
        from app.core.errors import ValidationAppError

        raise ValidationAppError("Provide linked_proposal_id or linked_position_id.")
    return journal_service.prefill(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        linked_proposal_id=linked_proposal_id,
        linked_position_id=linked_position_id,
    )


@router.get("/entries", response_model=PaginatedJournalEntries, summary="List journal entries")
async def list_journal_entries(
    tenant: TenantDep,
    journal_service: JournalServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedJournalEntries:
    items, total = journal_service.list_entries(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        limit=limit,
        offset=offset,
    )
    return PaginatedJournalEntries(items=items, total=total, limit=limit, offset=offset)


@router.get("/entries/{journal_entry_id}", response_model=JournalEntry)
async def get_journal_entry(
    journal_entry_id: uuid.UUID,
    tenant: TenantDep,
    journal_service: JournalServiceDep,
) -> JournalEntry:
    entry = journal_service.get(journal_entry_id)
    ensure_same_organization(entry.organization_id, tenant)
    return entry


@router.patch("/entries/{journal_entry_id}", response_model=JournalEntry)
async def update_journal_entry(
    journal_entry_id: uuid.UUID,
    body: JournalEntryUpdate,
    tenant: TraderDep,
    journal_service: JournalServiceDep,
    session: SessionDep,
) -> JournalEntry:
    entry = journal_service.get(journal_entry_id)
    ensure_same_organization(entry.organization_id, tenant)
    result = journal_service.update(journal_entry_id, body)
    session.commit()
    return result


@router.delete("/entries/{journal_entry_id}", status_code=204)
async def delete_journal_entry(
    journal_entry_id: uuid.UUID,
    tenant: TraderDep,
    journal_service: JournalServiceDep,
    session: SessionDep,
) -> None:
    entry = journal_service.get(journal_entry_id)
    ensure_same_organization(entry.organization_id, tenant)
    journal_service.delete(journal_entry_id)
    session.commit()


@router.get(
    "/entries/{journal_entry_id}/discipline-analysis",
    response_model=DisciplineAnalysis,
    summary="Discipline analysis for journal entry",
)
async def journal_discipline_analysis(
    journal_entry_id: uuid.UUID,
    tenant: TraderDep,
    journal_service: JournalServiceDep,
    hvs_service: HumanVsSystemServiceDep,
) -> DisciplineAnalysis:
    entry = journal_service.get(journal_entry_id)
    ensure_same_organization(entry.organization_id, tenant)
    return hvs_service.analyze_discipline(
        journal_entry_id,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )


@router.post(
    "/entries/{journal_entry_id}/discipline-analysis/candidates",
    response_model=LessonCandidate,
    summary="Create lesson candidate from discipline analysis",
)
async def create_discipline_lesson_candidate(
    journal_entry_id: uuid.UUID,
    tenant: TraderDep,
    journal_service: JournalServiceDep,
    hvs_service: HumanVsSystemServiceDep,
    lesson_service: LessonCandidateServiceDep,
    session: SessionDep,
    category: str = Query(..., description="Suggestion category, e.g. early_exit"),
) -> LessonCandidate:
    entry = journal_service.get(journal_entry_id)
    ensure_same_organization(entry.organization_id, tenant)
    candidate_id = hvs_service.create_discipline_candidate(
        journal_entry_id,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        category=category,
    )
    session.commit()
    return lesson_service.get(
        candidate_id, organization_id=tenant.organization_id, user_id=tenant.user_id
    )
