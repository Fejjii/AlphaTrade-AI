"""Paper Watcher runtime status (monitoring only; no scans from HTTP)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from app.core.config import Settings
from app.core.dependencies import SessionDep, SettingsDep
from app.db.models import KillSwitchState
from app.schemas.watcher_paper import (
    WATCHER_PAPER_ACTIVATION_REQUIREMENTS,
    WatcherPaperRuntimeStatus,
    WatcherPaperScopeStatus,
)
from app.security.rate_limit import tenant_rate_limit_dependency
from app.security.rbac import ReaderDep
from app.workers.watcher_paper import paper_runtime_enabled
from app.workers.watcher_paper_targets import normalize_paper_symbols

router = APIRouter(prefix="/watcher", tags=["watcher-paper"])

_READ_LIMIT = Depends(tenant_rate_limit_dependency("watcher:read", limit=120, window_seconds=3600))


@router.get(
    "/paper-runtime/status",
    response_model=WatcherPaperRuntimeStatus,
    summary="Paper Watcher runtime status",
    dependencies=[_READ_LIMIT],
)
async def watcher_paper_runtime_status(
    request: Request,
    tenant: ReaderDep,
    settings: SettingsDep,
    session: SessionDep,
) -> WatcherPaperRuntimeStatus:
    runtime = getattr(request.app.state, "watcher_paper_runtime", None)
    enabled = paper_runtime_enabled(settings)
    snapshot = runtime.snapshot() if runtime is not None else None
    kill_active = _tenant_kill_switch_active(session, settings, tenant.organization_id)
    scopes: list[WatcherPaperScopeStatus] = []
    if snapshot is not None:
        for scan in snapshot.last_scans:
            if scan.organization_id != tenant.organization_id:
                continue
            scopes.append(
                WatcherPaperScopeStatus(
                    scan_scope=scan.scan_scope,
                    symbol=scan.symbol,
                    health_state=scan.health_state,
                    lease_owner=scan.lease_owner,
                    last_reason_code=scan.reason_code,
                    candidate_ids=[str(item) for item in scan.candidate_ids],
                )
            )
    return WatcherPaperRuntimeStatus(
        enabled=enabled if snapshot is None else snapshot.enabled,
        running=False if snapshot is None else snapshot.running,
        worker_id=None if snapshot is None else snapshot.worker_id,
        symbols=list(
            snapshot.symbols
            if snapshot is not None
            else normalize_paper_symbols(settings.watcher_paper_symbols)
        ),
        poll_interval_seconds=(
            snapshot.poll_interval_seconds
            if snapshot is not None
            else settings.watcher_paper_poll_interval_seconds
        ),
        max_scopes_per_cycle=(
            snapshot.max_scopes_per_cycle
            if snapshot is not None
            else settings.watcher_paper_max_scopes_per_cycle
        ),
        paper_only=True,
        real_trading_enabled=settings.real_trading_enabled,
        telegram_enabled=settings.telegram_interaction_enabled,
        kill_switch_active=kill_active,
        last_cycle_at=None if snapshot is None else snapshot.last_cycle_at,
        last_reason_code="idle" if snapshot is None else snapshot.last_reason_code,
        cycles_completed=0 if snapshot is None else snapshot.cycles_completed,
        scans_succeeded=0 if snapshot is None else snapshot.scans_succeeded,
        scans_failed=0 if snapshot is None else snapshot.scans_failed,
        scans_skipped=0 if snapshot is None else snapshot.scans_skipped,
        scans_blocked=0 if snapshot is None else snapshot.scans_blocked,
        candidates_created=0 if snapshot is None else snapshot.candidates_created,
        scopes=scopes,
        remaining_activation_requirements=list(WATCHER_PAPER_ACTIVATION_REQUIREMENTS),
    )


def _tenant_kill_switch_active(
    session: SessionDep, settings: Settings, organization_id: UUID
) -> bool:
    if settings.global_kill_switch_active:
        return True
    row = session.scalar(
        select(KillSwitchState).where(KillSwitchState.organization_id == organization_id)
    )
    return bool(row is not None and row.active)
