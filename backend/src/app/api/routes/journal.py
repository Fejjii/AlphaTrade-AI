"""Trade journal API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.auth import TenantDep
from app.core.dependencies import (
    HumanVsSystemServiceDep,
    JournalServiceDep,
    JournalTradeServiceDep,
    LessonCandidateServiceDep,
    SessionDep,
)
from app.schemas.common import JournalTradeSource, JournalTradeStatus
from app.schemas.human_vs_system import DisciplineAnalysis
from app.schemas.journal import (
    JournalEntry,
    JournalEntryCreate,
    JournalEntryPrefill,
    JournalEntryUpdate,
    PaginatedJournalEntries,
)
from app.schemas.journal_trades import (
    JournalTradeCreate,
    JournalTradeDetail,
    JournalTradeEvidenceCreate,
    JournalTradeEvidenceRead,
    JournalTradeObservationCreate,
    JournalTradeObservationRead,
    JournalTradeRead,
    JournalTradeRuleCheckCreate,
    JournalTradeRuleCheckRead,
    JournalTradeUpdate,
    PaginatedJournalTrades,
)
from app.schemas.lesson import LessonCandidate
from app.security.rbac import ReaderDep, TraderDep
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


# --------------------------------------------------------------------------- #
# Canonical journal trades (AT-030 — record-only, no execution authority)
# --------------------------------------------------------------------------- #


@router.post(
    "/trades",
    response_model=JournalTradeRead,
    status_code=201,
    summary="Create canonical journal trade",
)
async def create_journal_trade(
    body: JournalTradeCreate,
    tenant: TraderDep,
    service: JournalTradeServiceDep,
    session: SessionDep,
) -> JournalTradeRead:
    result = service.create(
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post(
    "/trades/from-position/{position_id}",
    response_model=JournalTradeRead,
    status_code=201,
    summary="Create journal trade prefilled from a paper position",
)
async def create_journal_trade_from_position(
    position_id: uuid.UUID,
    tenant: TraderDep,
    service: JournalTradeServiceDep,
    session: SessionDep,
) -> JournalTradeRead:
    result = service.create_from_position(
        position_id,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post(
    "/trades/from-paper-trade/{paper_trade_id}",
    response_model=JournalTradeRead,
    status_code=201,
    summary="Create journal trade prefilled from a paper-validation trade",
)
async def create_journal_trade_from_paper_trade(
    paper_trade_id: uuid.UUID,
    tenant: TraderDep,
    service: JournalTradeServiceDep,
    session: SessionDep,
) -> JournalTradeRead:
    result = service.create_from_paper_trade(
        paper_trade_id,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.get(
    "/trades",
    response_model=PaginatedJournalTrades,
    summary="List canonical journal trades",
)
async def list_journal_trades(
    tenant: ReaderDep,
    service: JournalTradeServiceDep,
    source: JournalTradeSource | None = Query(default=None),
    status: JournalTradeStatus | None = Query(default=None),
    symbol: str | None = Query(default=None, max_length=30),
    user_strategy_id: uuid.UUID | None = Query(default=None),
    setup_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedJournalTrades:
    items, total = service.list_trades(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        source=source,
        status=status,
        symbol=symbol,
        user_strategy_id=user_strategy_id,
        setup_id=setup_id,
        limit=limit,
        offset=offset,
    )
    return PaginatedJournalTrades(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/trades/{journal_trade_id}",
    response_model=JournalTradeDetail,
    summary="Get journal trade with evidence, rule checks, and observations",
)
async def get_journal_trade(
    journal_trade_id: uuid.UUID,
    tenant: ReaderDep,
    service: JournalTradeServiceDep,
) -> JournalTradeDetail:
    return service.get_detail(journal_trade_id, organization_id=tenant.organization_id)


@router.patch(
    "/trades/{journal_trade_id}",
    response_model=JournalTradeRead,
    summary="Update canonical journal trade",
)
async def update_journal_trade(
    journal_trade_id: uuid.UUID,
    body: JournalTradeUpdate,
    tenant: TraderDep,
    service: JournalTradeServiceDep,
    session: SessionDep,
) -> JournalTradeRead:
    result = service.update(
        journal_trade_id,
        body,
        organization_id=tenant.organization_id,
    )
    session.commit()
    return result


@router.delete(
    "/trades/{journal_trade_id}",
    status_code=204,
    summary="Delete canonical journal trade",
)
async def delete_journal_trade(
    journal_trade_id: uuid.UUID,
    tenant: TraderDep,
    service: JournalTradeServiceDep,
    session: SessionDep,
) -> None:
    service.delete(journal_trade_id, organization_id=tenant.organization_id)
    session.commit()


@router.post(
    "/trades/{journal_trade_id}/evidence",
    response_model=JournalTradeEvidenceRead,
    status_code=201,
    summary="Attach evidence to a journal trade",
)
async def add_journal_trade_evidence(
    journal_trade_id: uuid.UUID,
    body: JournalTradeEvidenceCreate,
    tenant: TraderDep,
    service: JournalTradeServiceDep,
    session: SessionDep,
) -> JournalTradeEvidenceRead:
    result = service.add_evidence(
        journal_trade_id,
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post(
    "/trades/{journal_trade_id}/rule-checks",
    response_model=JournalTradeRuleCheckRead,
    status_code=201,
    summary="Record a rule-compliance check for a journal trade",
)
async def add_journal_trade_rule_check(
    journal_trade_id: uuid.UUID,
    body: JournalTradeRuleCheckCreate,
    tenant: TraderDep,
    service: JournalTradeServiceDep,
    session: SessionDep,
) -> JournalTradeRuleCheckRead:
    result = service.add_rule_check(
        journal_trade_id,
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post(
    "/trades/{journal_trade_id}/observations",
    response_model=JournalTradeObservationRead,
    status_code=201,
    summary="Record a behavioral observation for a journal trade",
)
async def add_journal_trade_observation(
    journal_trade_id: uuid.UUID,
    body: JournalTradeObservationCreate,
    tenant: TraderDep,
    service: JournalTradeServiceDep,
    session: SessionDep,
) -> JournalTradeObservationRead:
    result = service.add_observation(
        journal_trade_id,
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


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
