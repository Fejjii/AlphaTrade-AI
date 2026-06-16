"""Human versus system comparison API (Slice 33)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.dependencies import HumanVsSystemServiceDep
from app.schemas.human_vs_system import HumanVsSystemComparison
from app.security.rbac import TenantDep

router = APIRouter(prefix="/human-vs-system", tags=["human-vs-system"])


@router.get("/{trade_id}", response_model=HumanVsSystemComparison, summary="Compare trade to plan")
async def compare_human_vs_system(
    trade_id: uuid.UUID,
    tenant: TenantDep,
    service: HumanVsSystemServiceDep,
) -> HumanVsSystemComparison:
    return service.compare(
        trade_id,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
