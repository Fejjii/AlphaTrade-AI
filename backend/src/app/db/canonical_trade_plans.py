"""ORM models for canonical TradePlan roots, lineage, and idempotency.

Lineage lives beside ``trade_plan_revisions.semantic_payload`` so Phase 1
``CanonicalTradePlanContentV1`` hashes stay unchanged. Legacy PVC-backed
revisions remain in ``trade_plan_revisions`` with ``plan_authority=paper_validation``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    event,
)
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from app.core.errors import ValidationAppError
from app.db.base import Base

_registered = False

PLAN_AUTHORITY_PAPER_VALIDATION = "paper_validation"
PLAN_AUTHORITY_CANONICAL = "canonical"
PLAN_ROOT_ANALYSIS = "analysis_proposal"
PLAN_ROOT_CANONICAL = "canonical_plan_root"


class CanonicalTradePlanHistoryImmutabilityError(ValidationAppError):
    code = "canonical_trade_plan_history_immutable"


class CanonicalTradePlanRootRow(Base):
    __tablename__ = "canonical_trade_plan_roots"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            "account_id",
            "candidate_id",
            name="uq_canonical_trade_plan_roots_scope",
        ),
        ForeignKeyConstraint(
            ["plan_id", "organization_id", "user_id"],
            ["trade_proposals.id", "trade_proposals.organization_id", "trade_proposals.user_id"],
            name="fk_canonical_plan_root_proposal",
        ),
        ForeignKeyConstraint(
            ["account_id", "organization_id", "user_id"],
            [
                "execution_accounts.id",
                "execution_accounts.organization_id",
                "execution_accounts.user_id",
            ],
            name="fk_canonical_plan_root_account",
        ),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("canonical_candidates.candidate_id", name="fk_canonical_plan_root_candidate"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CanonicalTradePlanLineageRow(Base):
    __tablename__ = "canonical_trade_plan_lineage"
    __table_args__ = (
        UniqueConstraint("uniqueness_hash", name="uq_canonical_trade_plan_lineage_hash"),
        CheckConstraint(
            "length(uniqueness_hash) = 64", name="canonical_trade_plan_lineage_uniqueness_len"
        ),
        CheckConstraint(
            "length(envelope_content_hash) = 64",
            name="canonical_trade_plan_lineage_envelope_len",
        ),
    )

    revision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("trade_plan_revisions.id", name="fk_canonical_plan_lineage_revision"),
        primary_key=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("canonical_candidates.candidate_id", name="fk_canonical_plan_lineage_candidate"),
        nullable=False,
    )
    candidate_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    assessment_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    eligibility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "action_eligibility_evaluations.eligibility_id",
            name="fk_canonical_plan_lineage_eligibility",
        ),
        nullable=False,
    )
    eligibility_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    eligibility_uniqueness_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_window_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    setup_definition_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    compiled_setup_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fusion_policy_version: Mapped[str] = mapped_column(String(120), nullable=False)
    uniqueness_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    envelope_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class CanonicalTradePlanIdempotencyKeyRow(Base):
    __tablename__ = "canonical_trade_plan_idempotency_keys"
    __table_args__ = (
        CheckConstraint(
            "length(uniqueness_hash) = 64",
            name="canonical_trade_plan_idempotency_keys_hash_len",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    uniqueness_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("trade_plan_revisions.id", name="fk_canonical_plan_idempotency_revision"),
        nullable=False,
    )


def _forbid_history_mutation(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    raise CanonicalTradePlanHistoryImmutabilityError(
        f"{type(target).__name__} rows are append-only and cannot be updated.",
        details={"model": type(target).__name__},
    )


def _forbid_history_delete(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    raise CanonicalTradePlanHistoryImmutabilityError(
        f"{type(target).__name__} rows are append-only and cannot be deleted.",
        details={"model": type(target).__name__},
    )


def register_canonical_trade_plan_immutability() -> None:
    global _registered
    if _registered:
        return
    for model in (
        CanonicalTradePlanRootRow,
        CanonicalTradePlanLineageRow,
        CanonicalTradePlanIdempotencyKeyRow,
    ):
        event.listen(model, "before_update", _forbid_history_mutation)
        event.listen(model, "before_delete", _forbid_history_delete)
    _registered = True
