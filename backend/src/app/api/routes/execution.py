"""Execution API — paper mode only."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.core.auth import TenantDep
from app.core.dependencies import (
    ExecutionServiceDep,
    ProposalServiceDep,
    SessionDep,
    UsageServiceDep,
)
from app.schemas.execution import PaginatedPaperOrders, PaperOrder, PaperOrderRequest
from app.security.quota_enforcement import require_quota
from app.security.rate_limit import tenant_rate_limit_dependency
from app.security.rbac import TraderDep
from app.security.tenant import ensure_same_organization

router = APIRouter(prefix="/execution", tags=["execution"])

_EXECUTION_RATE_LIMIT = Depends(
    tenant_rate_limit_dependency(
        "execution:paper",
        limit=30,
        window_seconds=3600,
        ip_limit=60,
        user_limit=30,
    )
)
_PAPER_EXECUTION_QUOTA = require_quota("paper_execution")


@router.post(
    "/paper",
    response_model=PaperOrder,
    summary="Place a paper order",
    dependencies=[_EXECUTION_RATE_LIMIT, _PAPER_EXECUTION_QUOTA],
)
async def place_paper_order(
    body: PaperOrderRequest,
    tenant: TraderDep,
    proposal_service: ProposalServiceDep,
    execution_service: ExecutionServiceDep,
    usage_service: UsageServiceDep,
    session: SessionDep,
) -> PaperOrder:
    proposal = proposal_service.get(body.proposal_id)
    ensure_same_organization(proposal.organization_id, tenant)
    result = execution_service.place_paper_order(body)
    from app.schemas.usage import UsageEventCreate

    # One authoritative commit: business + audit (flushed in service) + usage.
    usage_service.record(
        UsageEventCreate(
            request_id=str(body.idempotency_key),
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            feature="paper_execution",
            provider="paper-engine",
            input_tokens=0,
            output_tokens=0,
            provider_metadata={"cost_source": "unavailable"},
        )
    )
    session.commit()
    return result


@router.get("/orders", response_model=PaginatedPaperOrders, summary="List paper orders")
async def list_orders(
    tenant: TenantDep,
    execution_service: ExecutionServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedPaperOrders:
    items, total = execution_service.list_orders(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        limit=limit,
        offset=offset,
    )
    return PaginatedPaperOrders(items=items, total=total, limit=limit, offset=offset)


@router.get("/orders/{order_id}", response_model=PaperOrder, summary="Get paper order")
async def get_order(
    order_id: uuid.UUID,
    tenant: TenantDep,
    execution_service: ExecutionServiceDep,
) -> PaperOrder:
    order = execution_service.get_order(order_id)
    ensure_same_organization(order.organization_id, tenant)
    return order
