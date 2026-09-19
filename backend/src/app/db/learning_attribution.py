"""ORM models for durable Phase 8 learning attribution.

Records are the current candidate-scoped projection. Events are append-only
source-identity evidence. These tables are not a JournalTrade writer and are
not wired into FastAPI, Watcher, Telegram, or execution.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    text,
)
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from app.core.errors import ConflictError, ValidationAppError
from app.db.base import Base, TimestampMixin

_registered = False

_IDENTITY_ATTRS = (
    "organization_id",
    "candidate_id",
    "assessment_id",
    "evidence_window_hash",
    "uniqueness_tuple_hash",
    "learning_venue_mode",
)
_STICKY_ONCE_ATTRS = ("execution_lifecycle_id", "journal_trade_id")


class LearningAttributionHistoryImmutabilityError(ValidationAppError):
    code = "learning_attribution_history_immutable"


class LearningAttributionIdentityMutationError(ConflictError):
    """Identity columns on the attribution aggregate cannot be rewritten."""

    code = "learning_attribution_identity_immutable"


class LearningAttributionRecordRow(TimestampMixin, Base):
    __tablename__ = "learning_attribution_records"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "candidate_id",
            name="uq_learning_attribution_records_org_candidate",
        ),
        Index(
            "uq_learning_attribution_records_org_lifecycle",
            "organization_id",
            "execution_lifecycle_id",
            unique=True,
            postgresql_where=text("execution_lifecycle_id IS NOT NULL"),
            sqlite_where=text("execution_lifecycle_id IS NOT NULL"),
        ),
        CheckConstraint(
            "length(evidence_window_hash) = 64",
            name="learning_attribution_records_window_hash_len",
        ),
        CheckConstraint(
            "length(uniqueness_tuple_hash) = 64",
            name="learning_attribution_records_uniqueness_len",
        ),
        CheckConstraint(
            "length(candidate_content_hash) = 64",
            name="learning_attribution_records_candidate_hash_len",
        ),
        CheckConstraint(
            "length(facts_hash) = 64",
            name="learning_attribution_records_facts_hash_len",
        ),
        CheckConstraint(
            "learning_venue_mode IN ('paper_internal', 'paper_exchange_demo')",
            name="learning_attribution_records_venue_mode",
        ),
        CheckConstraint(
            "(NOT executed_trade_outcome) OR (journal_trade_id IS NOT NULL)",
            name="learning_attribution_records_executed_has_trade",
        ),
        CheckConstraint(
            "NOT (executed_trade_outcome AND rejected)",
            name="learning_attribution_records_reject_not_executed",
        ),
        CheckConstraint(
            "NOT (executed_trade_outcome AND skipped)",
            name="learning_attribution_records_skip_not_executed",
        ),
        Index(
            "ix_learning_attribution_records_org_strategy_setup",
            "organization_id",
            "strategy_version_id",
            "setup_definition_id",
            "learning_venue_mode",
        ),
        Index(
            "ix_learning_attribution_records_org_venue",
            "organization_id",
            "learning_venue_mode",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id", name="fk_learning_attr_records_org"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", name="fk_learning_attr_records_user"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    assessment_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    evidence_window_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    uniqueness_tuple_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_lifecycle_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    journal_trade_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("journal_trades.id", name="fk_learning_attr_records_journal_trade"),
        nullable=True,
    )
    trade_plan_revision_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    facts_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    executed_trade_outcome: Mapped[bool] = mapped_column(Boolean, nullable=False)
    learning_venue_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    setup_quality_axis: Mapped[str] = mapped_column(String(32), nullable=False)
    execution_quality_axis: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_adherence_axis: Mapped[str] = mapped_column(String(32), nullable=False)
    trader_behavior_axis: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_actor: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    setup_definition_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    fusion_policy_version: Mapped[str] = mapped_column(String(120), nullable=False)
    rejected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    skipped: Mapped[bool] = mapped_column(Boolean, nullable=False)
    plan_approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    filled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    closed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    win: Mapped[bool] = mapped_column(Boolean, nullable=False)
    loss: Mapped[bool] = mapped_column(Boolean, nullable=False)
    breakeven: Mapped[bool] = mapped_column(Boolean, nullable=False)
    facts_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    narrative_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)


class LearningAttributionEventRow(Base):
    __tablename__ = "learning_attribution_events"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "account_id",
            "source_system",
            "source_aggregate",
            "event_type",
            "source_event_id",
            "source_event_version",
            "supersession",
            name="uq_learning_attribution_events_source",
        ),
        UniqueConstraint(
            "attribution_id",
            "event_index",
            name="uq_learning_attribution_events_index",
        ),
        CheckConstraint(
            "length(event_content_hash) = 64",
            name="learning_attribution_events_event_hash_len",
        ),
        CheckConstraint(
            "length(facts_hash) = 64",
            name="learning_attribution_events_facts_hash_len",
        ),
        CheckConstraint(
            "event_index >= 1",
            name="learning_attribution_events_index_min",
        ),
        Index(
            "ix_learning_attribution_events_org_attribution",
            "organization_id",
            "attribution_id",
            "event_index",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    attribution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "learning_attribution_records.id",
            name="fk_learning_attr_events_record",
        ),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id", name="fk_learning_attr_events_org"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    event_index: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    source_aggregate: Mapped[str] = mapped_column(String(160), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    source_event_version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersession: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    facts_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    journal_trade_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    payload_lineage: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    projection: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    narrative_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _history(target: object, attr: str) -> Any:
    state = sa_inspect(target)
    if state is None:
        raise RuntimeError("Missing ORM state for learning attribution identity check.")
    return state.get_history(attr, True)


def _forbid_identity_mutation(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    for attr in _IDENTITY_ATTRS:
        history = _history(target, attr)
        if not history.has_changes():
            continue
        raise LearningAttributionIdentityMutationError(
            "Learning attribution identity columns cannot be rewritten.",
            details={"reason": "attribution_identity_immutable", "field": attr},
        )
    for attr in _STICKY_ONCE_ATTRS:
        history = _history(target, attr)
        if not history.has_changes():
            continue
        old = history.deleted[0] if history.deleted else None
        new = history.added[0] if history.added else None
        if old is not None and old != new:
            raise LearningAttributionIdentityMutationError(
                "Learning attribution lifecycle bindings are sticky.",
                details={"reason": "attribution_binding_sticky", "field": attr},
            )


def _forbid_event_mutation(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    raise LearningAttributionHistoryImmutabilityError(
        "Learning attribution events are append-only and cannot be updated.",
        details={"model": type(target).__name__},
    )


def _forbid_event_delete(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    raise LearningAttributionHistoryImmutabilityError(
        "Learning attribution events are append-only and cannot be deleted.",
        details={"model": type(target).__name__},
    )


def register_learning_attribution_immutability() -> None:
    """Idempotent listener registration. Called after ORM maps are defined."""

    global _registered
    if _registered:
        return
    event.listen(LearningAttributionRecordRow, "before_update", _forbid_identity_mutation)
    event.listen(LearningAttributionEventRow, "before_update", _forbid_event_mutation)
    event.listen(LearningAttributionEventRow, "before_delete", _forbid_event_delete)
    _registered = True
