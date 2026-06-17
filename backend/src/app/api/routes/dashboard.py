"""Dashboard summary API (Slice 44)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import DashboardSummaryServiceDep
from app.schemas.dashboard import DashboardSummary
from app.security.rate_limit import tenant_rate_limit_dependency
from app.security.rbac import ReaderDep

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_DASHBOARD_READ_LIMIT = Depends(
    tenant_rate_limit_dependency("dashboard:read", limit=120, window_seconds=3600, user_limit=120)
)


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Paper-only dashboard summary",
    dependencies=[_DASHBOARD_READ_LIMIT],
)
async def dashboard_summary(
    tenant: ReaderDep,
    service: DashboardSummaryServiceDep,
) -> DashboardSummary:
    return service.summarize(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
