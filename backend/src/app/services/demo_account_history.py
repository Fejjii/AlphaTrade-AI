"""Venue-specific entry history; internal paper commands confer no demo authority."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ExecutionCommand, GovernedDemoLifecycleResolution, TradePlanRevision
from app.schemas.execution_protocol import ExecutionCommandOutcome


def has_demo_entry_history(session: Session, *, organization_id: UUID, account_id: UUID) -> bool:
    """Fail closed on demo ALLOW without immutable audited lifecycle resolution.

    The caller of the claim predicate holds the account safety epoch lock. The
    immutable, composite-bound plan is the venue authority; no mutable Journal
    state or client-supplied venue string can release this gate.
    Internal paper exposure still participates in the existing risk predicate.
    """
    return (
        session.scalar(
            select(ExecutionCommand.id)
            .join(TradePlanRevision, TradePlanRevision.id == ExecutionCommand.revision_id)
            .outerjoin(
                GovernedDemoLifecycleResolution,
                (GovernedDemoLifecycleResolution.command_id == ExecutionCommand.id)
                & (
                    GovernedDemoLifecycleResolution.organization_id
                    == ExecutionCommand.organization_id
                )
                & (GovernedDemoLifecycleResolution.account_id == ExecutionCommand.account_id)
                & (GovernedDemoLifecycleResolution.user_id == ExecutionCommand.user_id)
                & (GovernedDemoLifecycleResolution.revision_id == ExecutionCommand.revision_id),
            )
            .where(
                ExecutionCommand.organization_id == organization_id,
                ExecutionCommand.account_id == account_id,
                ExecutionCommand.outcome == ExecutionCommandOutcome.ALLOW,
                TradePlanRevision.execution_venue == "BLOFIN_DEMO",
                GovernedDemoLifecycleResolution.id.is_(None),
            )
            .limit(1)
        )
        is not None
    )
