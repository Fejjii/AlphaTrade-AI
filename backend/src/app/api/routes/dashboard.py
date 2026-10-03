"""Dashboard summary API (Slice 44)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.attention.contracts import AttentionQueue
from app.attention.reader import AttentionQueueService
from app.core.dependencies import DashboardSummaryServiceDep, SessionDep
from app.daily_review.contracts import DailyReview
from app.daily_review.reader import DailyReviewService
from app.daily_review.service import daily_window
from app.schemas.dashboard import DashboardSummary
from app.security.rate_limit import tenant_rate_limit_dependency
from app.security.rbac import ReaderDep

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_DASHBOARD_READ_LIMIT = Depends(
    tenant_rate_limit_dependency("dashboard:read", limit=120, window_seconds=3600, user_limit=120)
)


@router.get(
    "/attention",
    response_model=AttentionQueue,
    summary="Read-only paper attention queue for the current tenant and user",
    dependencies=[_DASHBOARD_READ_LIMIT],
)
def attention_queue(tenant: ReaderDep, session: SessionDep, response: Response) -> AttentionQueue:
    response.headers["Cache-Control"] = "private, no-store"
    return AttentionQueueService(session).queue(
        organization_id=tenant.organization_id, user_id=tenant.user_id, now=datetime.now(UTC)
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


@router.get(
    "/daily-review",
    response_model=DailyReview,
    summary="Recorded Daily Review for the current tenant and user",
    dependencies=[_DASHBOARD_READ_LIMIT],
)
def daily_review(
    tenant: ReaderDep,
    session: SessionDep,
    response: Response,
    day: date | None = Query(default=None, alias="date"),
    timezone: str = Query(default="UTC", min_length=1, max_length=100),
) -> DailyReview:
    try:
        zone = ZoneInfo(timezone)
        generated_at = datetime.now(UTC)
        window = daily_window(day or generated_at.astimezone(zone).date(), timezone)
    except (ZoneInfoNotFoundError, ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail="Invalid review date or timezone.") from exc
    response.headers["Cache-Control"] = "private, no-store"
    return DailyReviewService(session).review(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        window=window,
        generated_at=generated_at,
    )
