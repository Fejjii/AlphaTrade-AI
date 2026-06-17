"""Paper validation alert API (Slice 40 — storage only, no delivery)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import PaperAlertServiceDep, SessionDep
from app.schemas.alerts import PaginatedPaperAlerts, PaperAlert, PaperAlertSummary
from app.schemas.common import PaperAlertSeverity, PaperAlertType
from app.security.rate_limit import tenant_rate_limit_dependency
from app.security.rbac import ReaderDep, TraderDep

router = APIRouter(prefix="/alerts", tags=["alerts"])

_ALERTS_READ_LIMIT = Depends(
    tenant_rate_limit_dependency("alerts:read", limit=120, window_seconds=3600, user_limit=120)
)
_ALERTS_WRITE_LIMIT = Depends(
    tenant_rate_limit_dependency("alerts:write", limit=60, window_seconds=3600, user_limit=60)
)


@router.get(
    "",
    response_model=PaginatedPaperAlerts,
    summary="List paper validation alerts",
    dependencies=[_ALERTS_READ_LIMIT],
)
async def list_alerts(
    tenant: ReaderDep,
    service: PaperAlertServiceDep,
    alert_type: PaperAlertType | None = None,
    severity: PaperAlertSeverity | None = None,
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedPaperAlerts:
    return service.list_alerts(
        tenant.organization_id,
        alert_type=alert_type,
        severity=severity,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/summary",
    response_model=PaperAlertSummary,
    summary="Alert summary counts",
    dependencies=[_ALERTS_READ_LIMIT],
)
async def alerts_summary(
    tenant: ReaderDep,
    service: PaperAlertServiceDep,
) -> PaperAlertSummary:
    return service.summary(tenant.organization_id)


@router.get(
    "/{alert_id}",
    response_model=PaperAlert,
    summary="Get alert by id",
    dependencies=[_ALERTS_READ_LIMIT],
)
async def get_alert(
    alert_id: uuid.UUID,
    tenant: ReaderDep,
    service: PaperAlertServiceDep,
) -> PaperAlert:
    return service.get_alert(alert_id, organization_id=tenant.organization_id)


@router.patch(
    "/{alert_id}/read",
    response_model=PaperAlert,
    summary="Mark alert as read",
    dependencies=[_ALERTS_WRITE_LIMIT],
)
async def mark_alert_read(
    alert_id: uuid.UUID,
    tenant: TraderDep,
    service: PaperAlertServiceDep,
    session: SessionDep,
) -> PaperAlert:
    result = service.mark_read(alert_id, organization_id=tenant.organization_id)
    session.commit()
    return result


@router.patch("/read-all", summary="Mark all alerts as read", dependencies=[_ALERTS_WRITE_LIMIT])
async def mark_all_alerts_read(
    tenant: TraderDep,
    service: PaperAlertServiceDep,
    session: SessionDep,
) -> dict[str, int]:
    count = service.mark_all_read(tenant.organization_id)
    session.commit()
    return {"marked_read": count}
