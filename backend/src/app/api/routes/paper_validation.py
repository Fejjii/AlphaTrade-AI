"""Paper validation runtime API (Slice 39-40 — paper only)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import (
    PaperSchedulerServiceDep,
    PaperValidationRuntimeServiceDep,
    SessionDep,
)
from app.schemas.common import PaperTradeStatus
from app.schemas.paper_scheduler import (
    PaginatedPaperRuntimeHistory,
    PaperSchedulerConfigUpdate,
    PaperSchedulerStatus,
    PaperSchedulerTickResult,
)
from app.schemas.paper_validation import (
    PaginatedPaperPositions,
    PaginatedPaperSignals,
    PaginatedPaperTrades,
    PaperScanResult,
    PaperTickResult,
    PaperValidationMetrics,
    PaperValidationRun,
)
from app.security.rate_limit import tenant_rate_limit_dependency
from app.security.rbac import OwnerDep, TraderDep

router = APIRouter(prefix="/paper-validation", tags=["paper-validation"])

_PAPER_SCHEDULER_READ = Depends(
    tenant_rate_limit_dependency("paper-validation:scheduler:read", limit=120, window_seconds=3600)
)
_PAPER_SCHEDULER_WRITE = Depends(
    tenant_rate_limit_dependency("paper-validation:scheduler:write", limit=30, window_seconds=3600)
)
_PAPER_RUNTIME_WRITE = Depends(
    tenant_rate_limit_dependency("paper-validation:runtime:write", limit=60, window_seconds=3600)
)


@router.get(
    "/scheduler/status",
    response_model=PaperSchedulerStatus,
    summary="Paper validation scheduler status",
    dependencies=[_PAPER_SCHEDULER_READ],
)
async def get_scheduler_status(
    tenant: TraderDep,
    service: PaperSchedulerServiceDep,
) -> PaperSchedulerStatus:
    return service.get_status(organization_id=tenant.organization_id)


@router.post(
    "/scheduler/tick",
    response_model=PaperSchedulerTickResult,
    summary="Manual paper validation scheduler tick",
    dependencies=[_PAPER_SCHEDULER_WRITE],
)
async def scheduler_tick(
    tenant: OwnerDep,
    service: PaperSchedulerServiceDep,
    session: SessionDep,
) -> PaperSchedulerTickResult:
    result = service.tick(organization_id=tenant.organization_id, user_id=tenant.user_id)
    session.commit()
    return result


@router.patch(
    "/scheduler/config",
    response_model=PaperSchedulerStatus,
    summary="Update tenant paper scheduler config",
    dependencies=[_PAPER_SCHEDULER_WRITE],
)
async def update_scheduler_config(
    payload: PaperSchedulerConfigUpdate,
    tenant: OwnerDep,
    service: PaperSchedulerServiceDep,
    session: SessionDep,
) -> PaperSchedulerStatus:
    result = service.update_config(
        payload,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.get(
    "/scheduler/history",
    response_model=PaginatedPaperRuntimeHistory,
    summary="Scheduler and runtime cycle history",
    dependencies=[_PAPER_SCHEDULER_READ],
)
async def list_scheduler_history(
    tenant: TraderDep,
    service: PaperSchedulerServiceDep,
    run_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedPaperRuntimeHistory:
    return service.list_history(
        organization_id=tenant.organization_id,
        run_id=run_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{run_id}",
    response_model=PaperValidationRun,
    summary="Get paper validation run",
)
async def get_paper_validation_run(
    run_id: uuid.UUID,
    tenant: TraderDep,
    service: PaperValidationRuntimeServiceDep,
) -> PaperValidationRun:
    return service.get_run(run_id, organization_id=tenant.organization_id)


@router.post(
    "/{run_id}/scan",
    response_model=PaperScanResult,
    summary="Scan market for paper signals",
    dependencies=[_PAPER_RUNTIME_WRITE],
)
async def scan_paper_validation(
    run_id: uuid.UUID,
    tenant: TraderDep,
    service: PaperValidationRuntimeServiceDep,
    session: SessionDep,
) -> PaperScanResult:
    result = service.scan(
        run_id,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post(
    "/{run_id}/tick",
    response_model=PaperTickResult,
    summary="Advance paper trade monitoring (manual tick)",
    dependencies=[_PAPER_RUNTIME_WRITE],
)
async def tick_paper_validation(
    run_id: uuid.UUID,
    tenant: TraderDep,
    service: PaperValidationRuntimeServiceDep,
    session: SessionDep,
) -> PaperTickResult:
    result = service.tick(
        run_id,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post(
    "/{run_id}/stop",
    response_model=PaperValidationRun,
    summary="Stop paper validation run",
    dependencies=[_PAPER_RUNTIME_WRITE],
)
async def stop_paper_validation(
    run_id: uuid.UUID,
    tenant: TraderDep,
    service: PaperValidationRuntimeServiceDep,
    session: SessionDep,
) -> PaperValidationRun:
    result = service.stop(
        run_id,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.get(
    "/{run_id}/signals",
    response_model=PaginatedPaperSignals,
    summary="List paper signals for a run",
)
async def list_paper_signals(
    run_id: uuid.UUID,
    tenant: TraderDep,
    service: PaperValidationRuntimeServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedPaperSignals:
    return service.list_signals(
        run_id,
        organization_id=tenant.organization_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{run_id}/trades",
    response_model=PaginatedPaperTrades,
    summary="List paper trades for a run",
)
async def list_paper_trades(
    run_id: uuid.UUID,
    tenant: TraderDep,
    service: PaperValidationRuntimeServiceDep,
    status: PaperTradeStatus | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedPaperTrades:
    return service.list_trades(
        run_id,
        organization_id=tenant.organization_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{run_id}/positions",
    response_model=PaginatedPaperPositions,
    summary="List open paper positions",
)
async def list_paper_positions(
    run_id: uuid.UUID,
    tenant: TraderDep,
    service: PaperValidationRuntimeServiceDep,
) -> PaginatedPaperPositions:
    items = service.list_open_positions(run_id, organization_id=tenant.organization_id)
    return PaginatedPaperPositions(items=items, total=len(items))


@router.get(
    "/{run_id}/metrics",
    response_model=PaperValidationMetrics,
    summary="Paper validation metrics for a run",
)
async def get_paper_validation_metrics(
    run_id: uuid.UUID,
    tenant: TraderDep,
    service: PaperValidationRuntimeServiceDep,
) -> PaperValidationMetrics:
    return service.get_metrics(run_id, organization_id=tenant.organization_id)
