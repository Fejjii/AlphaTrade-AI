"""Human approval workflow API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.auth import TenantDep
from app.core.dependencies import ApprovalServiceDep, SessionDep, WorkflowServiceDep
from app.schemas.approval import (
    ApprovalActionRequest,
    ApprovalDecisionRequest,
    ApprovalRequest,
    PaginatedApprovalRequests,
)
from app.schemas.common import ApprovalAction, ApprovalStatus
from app.schemas.workflow import ApprovalWorkflowView
from app.security.rbac import TraderDep
from app.security.tenant import ensure_same_organization

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=PaginatedApprovalRequests, summary="List approvals")
async def list_approvals(
    tenant: TenantDep,
    approval_service: ApprovalServiceDep,
    status: ApprovalStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedApprovalRequests:
    items, total = approval_service.list_approvals(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return PaginatedApprovalRequests(items=items, total=total, limit=limit, offset=offset)


@router.get("/{approval_id}", response_model=ApprovalRequest, summary="Get approval")
async def get_approval(
    approval_id: uuid.UUID,
    tenant: TenantDep,
    approval_service: ApprovalServiceDep,
) -> ApprovalRequest:
    approval = approval_service.get(approval_id)
    ensure_same_organization(approval.organization_id, tenant)
    return approval


@router.get(
    "/{approval_id}/workflow",
    response_model=ApprovalWorkflowView,
    summary="Get approval with linked proposal and paper execution eligibility",
)
async def get_approval_workflow(
    approval_id: uuid.UUID,
    tenant: TenantDep,
    workflow_service: WorkflowServiceDep,
) -> ApprovalWorkflowView:
    view = workflow_service.get_approval_workflow(approval_id)
    ensure_same_organization(view.approval.organization_id, tenant)
    return view


@router.post("/{approval_id}/approve", response_model=ApprovalRequest)
async def approve(
    approval_id: uuid.UUID,
    body: ApprovalActionRequest,
    tenant: TraderDep,
    approval_service: ApprovalServiceDep,
    session: SessionDep,
) -> ApprovalRequest:
    approval = approval_service.get(approval_id)
    ensure_same_organization(approval.organization_id, tenant)
    result = approval_service.decide(
        approval_id,
        ApprovalDecisionRequest(action=ApprovalAction.APPROVE, reason=body.reason),
    )
    session.commit()
    return result


@router.post("/{approval_id}/reject", response_model=ApprovalRequest)
async def reject(
    approval_id: uuid.UUID,
    body: ApprovalActionRequest,
    tenant: TraderDep,
    approval_service: ApprovalServiceDep,
    session: SessionDep,
) -> ApprovalRequest:
    approval = approval_service.get(approval_id)
    ensure_same_organization(approval.organization_id, tenant)
    result = approval_service.decide(
        approval_id,
        ApprovalDecisionRequest(action=ApprovalAction.REJECT, reason=body.reason),
    )
    session.commit()
    return result


@router.post("/{approval_id}/modify", response_model=ApprovalRequest)
async def modify(
    approval_id: uuid.UUID,
    body: ApprovalActionRequest,
    tenant: TraderDep,
    approval_service: ApprovalServiceDep,
    session: SessionDep,
) -> ApprovalRequest:
    approval = approval_service.get(approval_id)
    ensure_same_organization(approval.organization_id, tenant)
    result = approval_service.decide(
        approval_id,
        ApprovalDecisionRequest(
            action=ApprovalAction.MODIFY,
            reason=body.reason,
            modified_fields=body.modified_fields,
        ),
    )
    session.commit()
    return result


@router.post("/{approval_id}/needs-more-analysis", response_model=ApprovalRequest)
async def needs_more_analysis(
    approval_id: uuid.UUID,
    body: ApprovalActionRequest,
    tenant: TraderDep,
    approval_service: ApprovalServiceDep,
    session: SessionDep,
) -> ApprovalRequest:
    approval = approval_service.get(approval_id)
    ensure_same_organization(approval.organization_id, tenant)
    result = approval_service.decide(
        approval_id,
        ApprovalDecisionRequest(
            action=ApprovalAction.NEEDS_MORE_ANALYSIS,
            reason=body.reason,
        ),
    )
    session.commit()
    return result


@router.post("/{approval_id}/decide", response_model=ApprovalRequest)
async def decide_approval(
    approval_id: uuid.UUID,
    body: ApprovalDecisionRequest,
    tenant: TraderDep,
    approval_service: ApprovalServiceDep,
    session: SessionDep,
) -> ApprovalRequest:
    approval = approval_service.get(approval_id)
    ensure_same_organization(approval.organization_id, tenant)
    result = approval_service.decide(approval_id, body)
    session.commit()
    return result
