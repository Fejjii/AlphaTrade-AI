"""Alert delivery API extensions (Slice 41)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import AlertDeliveryServiceDep, PaperAlertServiceDep, SessionDep
from app.schemas.alert_delivery import (
    AlertDeliverPendingResult,
    AlertDeliverResult,
    AlertDeliveryStatusResponse,
    AlertDeliverySummary,
)
from app.schemas.alerts import PaginatedPaperAlerts, PaperAlert, PaperAlertSummary
from app.schemas.common import PaperAlertSeverity, PaperAlertType
from app.security.rate_limit import tenant_rate_limit_dependency
from app.security.rbac import OwnerDep, ReaderDep, TraderDep

router = APIRouter(prefix="/alerts", tags=["alerts"])

_ALERTS_READ_LIMIT = Depends(
    tenant_rate_limit_dependency("alerts:read", limit=120, window_seconds=3600, user_limit=120)
)
_ALERTS_WRITE_LIMIT = Depends(
    tenant_rate_limit_dependency("alerts:write", limit=60, window_seconds=3600, user_limit=60)
)
_ALERTS_DELIVER_LIMIT = Depends(
    tenant_rate_limit_dependency("alerts:deliver", limit=30, window_seconds=3600, user_limit=30)
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
    "/delivery-status",
    response_model=AlertDeliveryStatusResponse,
    summary="External alert delivery configuration status",
    dependencies=[_ALERTS_READ_LIMIT],
)
async def alert_delivery_status(
    tenant: ReaderDep,
    delivery: AlertDeliveryServiceDep,
) -> AlertDeliveryStatusResponse:
    return delivery.get_status()


@router.get(
    "/delivery-summary",
    response_model=AlertDeliverySummary,
    summary="Alert delivery status counts for tenant",
    dependencies=[_ALERTS_READ_LIMIT],
)
async def alert_delivery_summary(
    tenant: ReaderDep,
    delivery: AlertDeliveryServiceDep,
) -> AlertDeliverySummary:
    return delivery.delivery_summary(tenant.organization_id)


@router.post(
    "/deliver-pending",
    response_model=AlertDeliverPendingResult,
    summary="Deliver pending alerts (owner/admin)",
    dependencies=[_ALERTS_DELIVER_LIMIT],
)
async def deliver_pending_alerts(
    tenant: OwnerDep,
    delivery: AlertDeliveryServiceDep,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> AlertDeliverPendingResult:
    result = delivery.deliver_pending(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        limit=limit,
    )
    session.commit()
    return result


@router.patch("/read-all", summary="Mark all alerts as read", dependencies=[_ALERTS_WRITE_LIMIT])
async def mark_all_alerts_read(
    tenant: TraderDep,
    service: PaperAlertServiceDep,
    session: SessionDep,
) -> dict[str, int]:
    count = service.mark_all_read(tenant.organization_id, user_id=tenant.user_id)
    session.commit()
    return {"marked_read": count}


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
    result = service.mark_read(
        alert_id,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post(
    "/{alert_id}/deliver",
    response_model=AlertDeliverResult,
    summary="Deliver single alert externally (owner/admin)",
    dependencies=[_ALERTS_DELIVER_LIMIT],
)
async def deliver_alert(
    alert_id: uuid.UUID,
    tenant: OwnerDep,
    delivery: AlertDeliveryServiceDep,
    session: SessionDep,
) -> AlertDeliverResult:
    result = delivery.deliver_alert(
        alert_id,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result
