"""Deterministic journal projection for canonical paper execution events.

JournalLifecycleProjector remains the only JournalTrade writer. Callers invoke
this after a durable paper claim or fill; this module does not execute trades.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.core.operation_policy import PersistenceKind, assert_write_allowed
from app.schemas.journal_lifecycle import JournalLifecycleEventInput, JournalProjectionResult
from app.schemas.journal_trades import PlannedTarget
from app.schemas.trade_plan import TradePlanRevision

if TYPE_CHECKING:
    from app.services.journal_lifecycle_projector import JournalLifecycleProjector

CANONICAL_EXECUTION_SOURCE_SYSTEM = "canonical_paper_execution"


def canonical_planned_targets(plan: TradePlanRevision) -> list[dict[str, object]]:
    """Copy exact ordered prices/allocations without floats in immutable event hashes."""
    return [
        {
            "price": str(target.price.value),
            "size_fraction": str(target.quantity_fraction),
            "label": f"TP{target.order}",
        }
        for target in plan.risk_and_exits.targets
    ]


def journal_planned_targets(plan: TradePlanRevision) -> list[dict[str, object]]:
    """Convert canonical target values to the existing Journal read-model schema."""
    return [
        PlannedTarget.model_validate(target).model_dump(mode="json")
        for target in canonical_planned_targets(plan)
    ]


def project_canonical_execution_event(
    projector: JournalLifecycleProjector,
    *,
    event: JournalLifecycleEventInput,
    organization_id: UUID,
    user_id: UUID,
) -> JournalProjectionResult:
    """Project one paper-execution lifecycle event. Exact replay converges."""

    assert_write_allowed(PersistenceKind.JOURNAL)
    if event.source_system != CANONICAL_EXECUTION_SOURCE_SYSTEM:
        raise ValueError("Canonical paper execution journal events require the canonical source.")
    return projector.project(
        event,
        organization_id=organization_id,
        user_id=user_id,
        actor_user_id=user_id,
    )
