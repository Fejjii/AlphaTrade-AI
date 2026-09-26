"""Kill-switch contract for controlled automated paper operation.

Monitoring continues. The worker process stays up, heartbeats, and health keeps
reporting market source and the last scan. New automated paper actions stop:

- no new Candidate mint
- no paper workflow started from the Watcher
- no new Telegram outbox enqueue
- no Telegram delivery of queued automated messages

An unreadable switch is treated as active for those actions. The switch does
not place, cancel, or mutate an exchange order, and rollback does not clear it.

Telegram enrollment is not one of those actions. It does not mint a Candidate,
start a paper workflow, enqueue outbound trade notices, or deliver them.
Enrollment therefore does not treat an unrelated organization's
``KillSwitchState`` row as a process-wide pause. The ops global switch still
pauses enrollment. Delivery and Watcher scans stay bound to their own tenant.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import KillSwitchState


def automated_paper_actions_blocked(switch_active: bool) -> bool:
    """Return whether automated paper actions must not start."""

    return switch_active


def read_enrollment_runtime_kill_switch(settings: Settings | None) -> bool:
    """Pause Telegram enrollment only for the process-wide ops switch.

    Organization rows are intentionally ignored. Enrollment has no bound tenant
    until a token is presented, and completing a binding does not execute a
    trade or deliver an automated paper action. A missing settings object or a
    failed read fails closed. Callers that mint, scan, enqueue, or deliver must
    use :func:`read_kill_switch_active` for the bound organization.
    """

    try:
        if settings is None:
            return True
        return bool(settings.global_kill_switch_active)
    except Exception:
        return True


def read_process_kill_switch(session: Session | None, settings: Settings | None) -> bool:
    """Global switch, or any tenant switch. Fail closed when the read errors.

    Do not use this for Telegram enrollment. Any active organization row pauses
    every caller, including tenants whose own switch is off.
    """

    try:
        if settings is not None and settings.global_kill_switch_active:
            return True
        if session is None:
            return False
        active = session.scalar(
            select(KillSwitchState.id).where(KillSwitchState.active.is_(True)).limit(1)
        )
        return active is not None
    except Exception:
        return True


def read_kill_switch_active(
    session: Session | None,
    settings: Settings | None,
    organization_id: UUID,
) -> bool:
    """Read the global and tenant switches. Fail closed when the read errors."""

    try:
        if settings is not None and settings.global_kill_switch_active:
            return True
        if session is None:
            return False
        row = session.scalar(
            select(KillSwitchState).where(KillSwitchState.organization_id == organization_id)
        )
        return bool(row is not None and row.active)
    except Exception:
        return True
