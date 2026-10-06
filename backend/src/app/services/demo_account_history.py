"""Venue-specific entry history; internal paper commands confer no demo authority."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ExecutionCommand, TradePlanRevision
from app.schemas.execution_protocol import ExecutionCommandOutcome


def has_demo_entry_history(session: Session, *, organization_id: UUID, account_id: UUID) -> bool:
    """Fail closed on every prior demo ALLOW, including older demo policies.

    The caller of the claim predicate holds the account safety epoch lock. The
    immutable, composite-bound plan is the venue authority; no mutable Journal
    state or client-supplied venue string can release this first-entry gate.
    Internal paper exposure still participates in the existing risk predicate.
    """
    return (
        session.scalar(
            select(ExecutionCommand.id)
            .join(TradePlanRevision, TradePlanRevision.id == ExecutionCommand.revision_id)
            .where(
                ExecutionCommand.organization_id == organization_id,
                ExecutionCommand.account_id == account_id,
                ExecutionCommand.outcome == ExecutionCommandOutcome.ALLOW,
                TradePlanRevision.execution_venue == "BLOFIN_DEMO",
            )
            .limit(1)
        )
        is not None
    )
