"""Human-governed strategy learning on the existing strategy authorities."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.core.dependencies import SessionDep, SettingsDep
from app.schemas.conversation import StrategyProposalRecord
from app.schemas.governed_learning import (
    GovernedLearningList,
    GovernedLearningStatus,
    GovernedProposalCreate,
    LearningIdentity,
    LearningPromotionApproval,
    LearningRollbackApproval,
    LearningValidationEvidence,
)
from app.schemas.strategy_lifecycle import StrategyLifecycleEventRecord
from app.security.rbac import ReaderDep, TraderDep
from app.services.strategy_promotion import StrategyPromotionService
from app.services.strategy_proposal_service import StrategyProposalService

router = APIRouter(prefix="/governed-learning", tags=["governed-learning"])


@router.post("/strategies/{strategy_id}/proposals", response_model=StrategyProposalRecord)
def create_proposal(
    strategy_id: UUID, body: GovernedProposalCreate, tenant: TraderDep, session: SessionDep
) -> StrategyProposalRecord:
    result = StrategyProposalService(session).create_governed(
        strategy_id,
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post("/proposals/{proposal_id}/validation-request", response_model=StrategyProposalRecord)
def request_validation(
    proposal_id: UUID, body: LearningIdentity, tenant: TraderDep, session: SessionDep
) -> StrategyProposalRecord:
    result = StrategyProposalService(session).request_governed_validation(
        proposal_id,
        expected_content_hash=body.expected_content_hash,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.put("/proposals/{proposal_id}/validation-evidence", response_model=GovernedLearningStatus)
def validation_evidence(
    proposal_id: UUID,
    body: LearningValidationEvidence,
    tenant: TraderDep,
    session: SessionDep,
    settings: SettingsDep,
) -> GovernedLearningStatus:
    result = StrategyPromotionService(session, settings).record_validation(
        proposal_id,
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.get("/proposals/{proposal_id}", response_model=GovernedLearningStatus)
def proposal_status(
    proposal_id: UUID, tenant: ReaderDep, session: SessionDep, settings: SettingsDep
) -> GovernedLearningStatus:
    return StrategyPromotionService(session, settings).status(
        proposal_id,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )


@router.get("/proposals", response_model=GovernedLearningList)
def list_proposals(
    tenant: ReaderDep,
    session: SessionDep,
    settings: SettingsDep,
    strategy_id: UUID | None = None,
    limit: int = Query(10, ge=1, le=20),
    offset: int = Query(0, ge=0, le=10000),
) -> GovernedLearningList:
    return StrategyPromotionService(session, settings).list_status(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        strategy_id=strategy_id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/proposals/{proposal_id}/approve-paper-promotion", response_model=StrategyLifecycleEventRecord
)
def approve_promotion(
    proposal_id: UUID,
    body: LearningPromotionApproval,
    tenant: TraderDep,
    session: SessionDep,
    settings: SettingsDep,
) -> StrategyLifecycleEventRecord:
    result = StrategyPromotionService(session, settings).promote(
        proposal_id,
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post(
    "/strategies/{strategy_id}/rollback-paper", response_model=StrategyLifecycleEventRecord
)
def rollback_paper(
    strategy_id: UUID,
    body: LearningRollbackApproval,
    tenant: TraderDep,
    session: SessionDep,
    settings: SettingsDep,
) -> StrategyLifecycleEventRecord:
    result = StrategyPromotionService(session, settings).rollback(
        strategy_id,
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result
