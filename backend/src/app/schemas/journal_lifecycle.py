"""Phase 4 canonical journal lifecycle and venue-correction contracts.

Record-only: these schemas never carry execution authority. Candidate, REJECT,
and SKIP never create ``JournalTrade``. Venue facts are projector-owned.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import JournalLifecycleEventType, ORMModel, StrictModel

LINEAGE_PAYLOAD_KEY = "lineage"
"""Nested payload key for Candidate/SetupAssessment/TradePlan lineage.

Not a JournalTrade column in this wave. Agent 1 owns any later durable columns.
"""

LINEAGE_STICKY_KEYS = (
    "organization_id",
    "account_id",
    "execution_lifecycle_id",
    "candidate_id",
    "candidate_content_hash",
    "assessment_id",
    "assessment_content_hash",
    "evidence_window_hash",
    "trade_plan_revision_id",
    "trade_plan_content_hash",
    "setup_definition_id",
    "strategy_version_id",
    "fusion_policy_version",
    "uniqueness_tuple_hash",
)


class JournalLineagePayload(StrictModel):
    """Typed lineage carried on lifecycle events without new ORM columns.

    First-seen values are sticky for an execution lifecycle. Conflicting values
    fail closed. These fields must not be treated as execution authority.
    """

    organization_id: UUID | None = None
    account_id: UUID | None = None
    execution_lifecycle_id: UUID | None = None
    candidate_id: UUID | None = None
    candidate_content_hash: str | None = Field(default=None, min_length=64, max_length=64)
    assessment_id: UUID | None = None
    assessment_content_hash: str | None = Field(default=None, min_length=64, max_length=64)
    evidence_window_hash: str | None = Field(default=None, min_length=64, max_length=64)
    trade_plan_revision_id: UUID | None = None
    trade_plan_content_hash: str | None = Field(default=None, min_length=64, max_length=64)
    setup_definition_id: UUID | None = None
    strategy_version_id: UUID | None = None
    fusion_policy_version: str | None = Field(default=None, min_length=3, max_length=120)
    uniqueness_tuple_hash: str | None = Field(default=None, min_length=64, max_length=64)


class JournalLifecycleEventInput(StrictModel):
    """One projector input. Source identity is the idempotency key."""

    event_type: JournalLifecycleEventType
    execution_lifecycle_id: UUID | None = None
    source_system: str = Field(min_length=1, max_length=80)
    source_aggregate: str = Field(min_length=1, max_length=160)
    source_event_id: str = Field(min_length=1, max_length=160)
    source_event_version: int = Field(ge=1)
    supersession: int = Field(default=0, ge=0)
    account_id: UUID
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
