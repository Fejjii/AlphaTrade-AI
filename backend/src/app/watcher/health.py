"""Worker health projection: healthy, degraded, blocked, stale."""

from __future__ import annotations

from datetime import datetime

from app.watcher.contracts import (
    ScanAttempt,
    ScanAttemptStatus,
    WatcherHealthSnapshot,
    WatcherHealthState,
    WatcherHeartbeat,
    WatcherRuntimeConfig,
    WorkerLease,
)


def project_health(
    *,
    scan_scope: str,
    config: WatcherRuntimeConfig,
    now: datetime,
    lease: WorkerLease | None,
    heartbeat: WatcherHeartbeat | None,
    latest_attempt: ScanAttempt | None,
) -> WatcherHealthSnapshot:
    if not config.enabled:
        return _snapshot(
            scan_scope=scan_scope,
            config=config,
            now=now,
            lease=lease,
            heartbeat=heartbeat,
            latest_attempt=latest_attempt,
            state=WatcherHealthState.BLOCKED,
            reason_code="watcher_disabled",
        )

    seconds_since_beat = _seconds_since(heartbeat.last_beat_at if heartbeat else None, now)
    stale_after = float(config.heartbeat_stale_after_seconds)
    lease_expired = (
        lease is None
        or lease.expires_at is None
        or lease.expires_at <= now
        or lease.owner_id is None
    )

    if heartbeat is None or seconds_since_beat is None or seconds_since_beat > stale_after:
        return _snapshot(
            scan_scope=scan_scope,
            config=config,
            now=now,
            lease=lease,
            heartbeat=heartbeat,
            latest_attempt=latest_attempt,
            state=WatcherHealthState.STALE,
            reason_code="heartbeat_stale" if heartbeat is not None else "heartbeat_missing",
            seconds_since_beat=seconds_since_beat,
        )

    if lease_expired:
        return _snapshot(
            scan_scope=scan_scope,
            config=config,
            now=now,
            lease=lease,
            heartbeat=heartbeat,
            latest_attempt=latest_attempt,
            state=WatcherHealthState.STALE,
            reason_code="lease_expired",
            seconds_since_beat=seconds_since_beat,
        )

    last_status = latest_attempt.status if latest_attempt is not None else None
    last_reason = latest_attempt.outcome_reason_code if latest_attempt is not None else None
    if last_status in {
        ScanAttemptStatus.REJECTED_STALE_FENCE,
        ScanAttemptStatus.CONVERGED_REPLAY,
    }:
        return _snapshot(
            scan_scope=scan_scope,
            config=config,
            now=now,
            lease=lease,
            heartbeat=heartbeat,
            latest_attempt=latest_attempt,
            state=WatcherHealthState.DEGRADED,
            reason_code=last_reason or last_status.value,
            seconds_since_beat=seconds_since_beat,
        )
    if last_status is ScanAttemptStatus.BLOCKED:
        return _snapshot(
            scan_scope=scan_scope,
            config=config,
            now=now,
            lease=lease,
            heartbeat=heartbeat,
            latest_attempt=latest_attempt,
            state=WatcherHealthState.BLOCKED,
            reason_code=last_reason or "blocked",
            seconds_since_beat=seconds_since_beat,
        )
    if last_status in {ScanAttemptStatus.DEGRADED, ScanAttemptStatus.FAILED}:
        return _snapshot(
            scan_scope=scan_scope,
            config=config,
            now=now,
            lease=lease,
            heartbeat=heartbeat,
            latest_attempt=latest_attempt,
            state=WatcherHealthState.DEGRADED,
            reason_code=last_reason or last_status.value,
            seconds_since_beat=seconds_since_beat,
        )
    if last_status is ScanAttemptStatus.STARTED:
        return _snapshot(
            scan_scope=scan_scope,
            config=config,
            now=now,
            lease=lease,
            heartbeat=heartbeat,
            latest_attempt=latest_attempt,
            state=WatcherHealthState.DEGRADED,
            reason_code="scan_in_progress",
            seconds_since_beat=seconds_since_beat,
        )

    return _snapshot(
        scan_scope=scan_scope,
        config=config,
        now=now,
        lease=lease,
        heartbeat=heartbeat,
        latest_attempt=latest_attempt,
        state=WatcherHealthState.HEALTHY,
        reason_code="healthy",
        seconds_since_beat=seconds_since_beat,
    )


def _seconds_since(stamp: datetime | None, now: datetime) -> float | None:
    if stamp is None:
        return None
    return (now - stamp).total_seconds()


def _snapshot(
    *,
    scan_scope: str,
    config: WatcherRuntimeConfig,
    now: datetime,
    lease: WorkerLease | None,
    heartbeat: WatcherHeartbeat | None,
    latest_attempt: ScanAttempt | None,
    state: WatcherHealthState,
    reason_code: str,
    seconds_since_beat: float | None = None,
) -> WatcherHealthSnapshot:
    return WatcherHealthSnapshot(
        state=state,
        scan_scope=scan_scope,
        enabled=config.enabled,
        lease_owner=lease.owner_id if lease is not None else None,
        lease_epoch=lease.lease_epoch if lease is not None else 0,
        fencing_token=lease.fencing_token if lease is not None else 0,
        lease_expires_at=lease.expires_at if lease is not None else None,
        last_beat_at=heartbeat.last_beat_at if heartbeat is not None else None,
        seconds_since_beat=seconds_since_beat,
        last_attempt_status=latest_attempt.status if latest_attempt is not None else None,
        last_lineage_id=latest_attempt.lineage_id if latest_attempt is not None else None,
        reason_code=reason_code,
        generated_at=now,
    )
