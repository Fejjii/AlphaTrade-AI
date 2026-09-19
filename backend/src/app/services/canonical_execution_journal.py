"""Deterministic journal projection for canonical paper execution events.

JournalLifecycleProjector remains the only JournalTrade writer. Callers invoke
this after a durable paper claim or fill; this module does not execute trades.
"""

from __future__ import annotations

from uuid import UUID

from app.core.operation_policy import PersistenceKind, assert_write_allowed
from app.schemas.journal_lifecycle import JournalLifecycleEventInput, JournalProjectionResult
from app.services.journal_lifecycle_projector import JournalLifecycleProjector

CANONICAL_EXECUTION_SOURCE_SYSTEM = "canonical_paper_execution"


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
