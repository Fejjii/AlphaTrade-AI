"""Barrier 3 commit linearization and provider-IO isolation.

Provider submission may only observe committed DISPATCH_AUTHORIZED rows and must
not run while the caller's ORM session holds an open write transaction.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.db.models import VenueSubmitEffect
from app.schemas.execution_protocol import CommittedDispatchAuthorization, VenueSubmitEffectState


def commit_barrier3(session: Session) -> None:
    """Commit the dispatch-authorization transaction. This is the send linearization."""

    session.flush()
    session.commit()


def require_idle_session_for_provider_io(session: Session) -> None:
    """Fail closed if the caller still has a write transaction, then close read txns."""

    if session.new or session.dirty or session.deleted:
        raise ConflictError(
            "Provider submission requires committed dispatch authorization "
            "and no pending database writes.",
            details={"reason": "send_blocked_open_database_transaction"},
        )
    if session.in_transaction():
        session.rollback()
    if session.in_transaction():
        raise ConflictError(
            "Provider submission requires no active database transaction.",
            details={"reason": "send_blocked_open_database_transaction"},
        )


def load_committed_dispatch_authorization(
    session: Session, command_id: uuid.UUID
) -> CommittedDispatchAuthorization | None:
    """Load Barrier 3 state from a separate session so uncommitted flushes are invisible."""

    bind = session.get_bind()
    with Session(bind) as probe:
        row = probe.scalar(
            select(VenueSubmitEffect).where(VenueSubmitEffect.command_id == command_id)
        )
        if row is None:
            snapshot = None
        else:
            snapshot = CommittedDispatchAuthorization(
                command_id=row.command_id,
                effect_id=row.id,
                client_order_id=row.client_order_id,
                state=row.state,
                lease_owner=row.lease_owner,
                fencing_token=int(row.fencing_token),
                dispatch_fencing_token=(
                    int(row.dispatch_fencing_token)
                    if row.dispatch_fencing_token is not None
                    else None
                ),
                dispatch_safety_epoch=(
                    int(row.dispatch_safety_epoch)
                    if row.dispatch_safety_epoch is not None
                    else None
                ),
                attempt=int(row.attempt),
            )
        if probe.in_transaction():
            probe.rollback()
    return snapshot


def require_committed_dispatch_authorization(
    snapshot: CommittedDispatchAuthorization | None,
    *,
    owner: str,
    fencing_token: int,
) -> CommittedDispatchAuthorization:
    if snapshot is None or snapshot.state is not VenueSubmitEffectState.DISPATCH_AUTHORIZED:
        raise ConflictError(
            "Send is forbidden until DISPATCH_AUTHORIZED commits.",
            details={
                "reason": "send_before_dispatch_authorization",
                "state": None if snapshot is None else snapshot.state.value,
            },
        )
    if snapshot.lease_owner != owner or snapshot.dispatch_fencing_token != fencing_token:
        raise ConflictError(
            "Stale worker cannot send after losing the lease fence.",
            details={"reason": "send_fence_mismatch"},
        )
    return snapshot
