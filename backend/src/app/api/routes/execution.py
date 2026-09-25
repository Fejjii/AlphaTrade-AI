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
from app.schemas.execution_protocol import (
    ClosePaperPlanHttpRequest,
    ClosePaperPlanRequest,
    ClosePaperPlanResult,
    ExecutePaperPlanHttpRequest,
    ExecutePaperPlanRequest,
    ExecutePaperPlanResult,
    ExecutionCommandOutcome,
)
from app.schemas.usage import UsageEventCreate
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
_PAPER_PLAN_RATE_LIMIT = Depends(
    tenant_rate_limit_dependency(
        "execution:paper-plan",
        limit=30,
        window_seconds=3600,
        ip_limit=60,
        user_limit=30,
    )
)


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
    proposal = proposal_service.get(
        body.proposal_id,
        organization_id=tenant.organization_id,
    )
    ensure_same_organization(proposal.organization_id, tenant)
    placement = execution_service.place_paper_order(body)

    # Replays and concurrent losers have no new unit-of-work to commit. The
    # convergence path already rolled back its dedicated request session.
    if not placement.created_new:
        return placement.order

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
    # One authoritative commit: business + audit (flushed in service) + usage.
    session.commit()
    return placement.order


@router.post(
    "/paper-plan",
    response_model=ExecutePaperPlanResult,
    summary="Execute an approved paper trade plan revision",
    dependencies=[_PAPER_PLAN_RATE_LIMIT, _PAPER_EXECUTION_QUOTA],
)
async def execute_paper_plan(
    body: ExecutePaperPlanHttpRequest,
    tenant: TraderDep,
    execution_service: ExecutionServiceDep,
    usage_service: UsageServiceDep,
    session: SessionDep,
) -> ExecutePaperPlanResult:
    result = execution_service.execute_paper_plan(
        ExecutePaperPlanRequest(
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            account_id=body.account_id,
            authorization_id=body.authorization_id,
            revision_id=body.revision_id,
            idempotency_key=body.idempotency_key,
            correlation_id=body.correlation_id,
        )
    )
    # Replay still commits so any healing journal/attribution writes in this
    # request survive process restart. Usage is metered only on first ALLOW.
    if not result.replayed and result.outcome is ExecutionCommandOutcome.ALLOW:
        usage_service.record(
            UsageEventCreate(
                request_id=body.idempotency_key,
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


@router.post(
    "/paper-plan/close",
    response_model=ClosePaperPlanResult,
    summary="Close a filled canonical paper plan and record the outcome",
    dependencies=[_PAPER_PLAN_RATE_LIMIT],
)
async def close_paper_plan(
    body: ClosePaperPlanHttpRequest,
    tenant: TraderDep,
    execution_service: ExecutionServiceDep,
    session: SessionDep,
) -> ClosePaperPlanResult:
    """Explicit paper exit. Does not read market data or place an exchange order."""

    result = execution_service.close_canonical_paper_plan(
        ClosePaperPlanRequest(
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            account_id=body.account_id,
            revision_id=body.revision_id,
            command_id=body.command_id,
            exit_price=body.exit_price,
            fees=body.fees,
            funding=body.funding,
            slippage=body.slippage,
            exit_reason=body.exit_reason,
            occurred_at=body.occurred_at,
            idempotency_key=body.idempotency_key,
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
