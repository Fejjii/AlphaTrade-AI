"""Heartbeat freshness for observed Watcher and Telegram runtime rows.

A persisted row is not a live worker. ``health_state`` is ``RUNNING`` only when
the heartbeat age is within the configured threshold. Age equal to the
threshold is fresh. A missing heartbeat is ``UNAVAILABLE``. A future heartbeat
(clock skew) or an older heartbeat is ``STALE`` and must not be reported as
running or available.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.health import WorkerComponentObservation, WorkerHealthState


def project_worker_component(
    row: object | None,
    *,
    now: datetime,
    stale_after_seconds: int,
) -> WorkerComponentObservation:
    """Project one status row into a freshness-adjusted health observation."""

    limit = stale_after_seconds
    if row is None:
        return _unavailable(limit)
    heartbeat_at = getattr(row, "heartbeat_at", None)
    health_state, age = classify_heartbeat(
        heartbeat_at if isinstance(heartbeat_at, datetime) else None,
        now=now,
        stale_after_seconds=limit,
    )
    persisted = str(getattr(row, "activation_state", "unknown"))
    return WorkerComponentObservation(
        available=health_state == "RUNNING",
        worker_id=str(getattr(row, "worker_id", "")),
        heartbeat_at=heartbeat_at if isinstance(heartbeat_at, datetime) else None,
        activation_state=_reported_activation(persisted, health_state),
        lease_owner=str(getattr(row, "lease_owner", "")),
        lease_epoch=int(getattr(row, "lease_epoch", 0)),
        lease_expires_at=getattr(row, "lease_expires_at", None),
        fence_held=bool(getattr(row, "fence_held", False)),
        last_scan_at=getattr(row, "last_scan_at", None),
        last_scan_reason=str(getattr(row, "last_scan_reason", "")),
        market_source=str(getattr(row, "market_source", "")),
        freshness_seconds=getattr(row, "freshness_seconds", None),
        telegram_runtime_state=str(getattr(row, "telegram_runtime_state", "absent")),
        inbound_mode=str(getattr(row, "inbound_mode", "off")),
        outbox_pending=int(getattr(row, "outbox_pending", 0)),
        outbox_retryable=int(getattr(row, "outbox_retryable", 0)),
        outbox_dead_letter=int(getattr(row, "outbox_dead_letter", 0)),
        last_delivery_at=getattr(row, "last_delivery_at", None),
        last_error_code=str(getattr(row, "last_error_code", "")),
        kill_switch_active=bool(getattr(row, "kill_switch_active", False)),
        request_count=int(getattr(row, "request_count", 0)),
        request_weight=int(getattr(row, "request_weight", 0)),
        rate_limited_count=int(getattr(row, "rate_limited_count", 0)),
        cache_hits=int(getattr(row, "cache_hits", 0)),
        health_state=health_state,
        heartbeat_age_seconds=age,
        heartbeat_stale_after_seconds=limit,
    )


def classify_heartbeat(
    heartbeat_at: datetime | None,
    *,
    now: datetime,
    stale_after_seconds: int,
) -> tuple[WorkerHealthState, float | None]:
    """Return liveness and age. Naive or future timestamps are not fresh."""

    if heartbeat_at is None:
        return "UNAVAILABLE", None
    if heartbeat_at.tzinfo is None or heartbeat_at.utcoffset() is None:
        return "STALE", None
    aware = now.tzinfo is not None and now.utcoffset() is not None
    observed = now if aware else now.replace(tzinfo=UTC)
    age = (observed - heartbeat_at.astimezone(UTC)).total_seconds()
    if age < 0 or age > float(stale_after_seconds):
        return "STALE", age
    return "RUNNING", age


def _reported_activation(persisted: str, health_state: WorkerHealthState) -> str:
    if health_state == "RUNNING":
        return persisted
    if persisted.strip().lower() == "running":
        return health_state
    return persisted


def _unavailable(stale_after_seconds: int) -> WorkerComponentObservation:
    return WorkerComponentObservation(
        available=False,
        health_state="UNAVAILABLE",
        heartbeat_age_seconds=None,
        heartbeat_stale_after_seconds=stale_after_seconds,
    )
