"""Phase 4 canonical journal lifecycle and venue-correction contracts.

Record-only: these schemas never carry execution authority. Candidate, REJECT,
and SKIP never create ``JournalTrade``. Venue facts are projector-owned.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import JournalLifecycleEventType, ORMModel, StrictModel


class JournalLifecycleEventInput(StrictModel):
    """One projector input. Source identity is the idempotency key."""

    event_type: JournalLifecycleEventType
    execution_lifecycle_id: UUID | None = None
    source_system: str = Field(min_length=1, max_length=80)
    source_aggregate: str = Field(min_length=1, max_length=160)
    source_event_id: str = Field(min_length=1, max_length=160)
    source_event_version: int = Field(ge=1)
    supersession: int = Field(default=0, ge=0)
    account_id: UUID | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, max_length=128)


class JournalProjectionResult(StrictModel):
    """Outcome of one projector call."""

    event_type: JournalLifecycleEventType
    journal_trade_id: UUID | None = None
    created_journal_trade: bool = False
    replayed: bool = False
    skipped_reason: str | None = None


class JournalVenueCorrectionRequest(StrictModel):
    """Append-only correction of projector-owned venue facts."""

    reason: str = Field(min_length=1, max_length=2000)
    fields: dict[str, object] = Field(min_length=1)


class JournalVenueCorrectionRead(ORMModel):
    id: UUID
    journal_trade_id: UUID
    organization_id: UUID
    field_name: str
    previous_value: object | None = None
    new_value: object | None = None
    reason: str
    actor_user_id: UUID | None = None
    content_hash: str
    created_at: datetime


class JournalMigrationParityReport(StrictModel):
    """Deterministic TradeJournal → JournalTrade parity snapshot."""

    organization_id: UUID | None = None
    legacy_count: int
    canonical_count: int
    row_count_parity: bool
    linked_proposal_legacy: int
    linked_proposal_canonical: int
    linked_position_legacy: int
    linked_position_canonical: int
    emotion_parity: bool
    mistake_parity: bool
    attachment_parity: bool
    unmatched_legacy_ids: list[UUID] = Field(default_factory=list)
