"""Performance analytics API (Slice 62, read + snapshot)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.dependencies import PerformanceServiceDep, SessionDep
from app.schemas.performance import PerformanceReport, PerformanceSnapshotResponse
from app.security.rbac import OwnerDep, ReaderDep

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/report", response_model=PerformanceReport, summary="Account performance report")
async def get_performance_report(
    tenant: ReaderDep,
    performance: PerformanceServiceDep,
) -> PerformanceReport:
    return performance.build_report(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )


@router.post(
    "/snapshot",
    response_model=PerformanceSnapshotResponse,
    summary="Persist an account performance snapshot",
)
async def create_performance_snapshot(
    tenant: OwnerDep,
    performance: PerformanceServiceDep,
    session: SessionDep,
) -> PerformanceSnapshotResponse:
    snapshot = performance.snapshot_account(organization_id=tenant.organization_id)
    session.commit()
    return PerformanceSnapshotResponse.model_validate(snapshot)
