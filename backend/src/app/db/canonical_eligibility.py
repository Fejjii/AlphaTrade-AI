"""ORM models for durable ActionEligibility evaluations.

Evaluations are immutable and keyed by uniqueness hash. Identity bindings keep
risk/safety/venue/assessment fingerprints fail-closed. These tables are not
wired into FastAPI, workers, or feature flags.
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
    UniqueConstraint,
    Uuid,
    event,
)
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from app.core.errors import ValidationAppError
from app.db.base import Base

_registered = False


class CanonicalEligibilityHistoryImmutabilityError(ValidationAppError):
    code = "canonical_eligibility_history_immutable"


class ActionEligibilityEvaluationRow(Base):
    __tablename__ = "action_eligibility_evaluations"
    __table_args__ = (
        UniqueConstraint("uniqueness_hash", name="uq_action_eligibility_evaluations_hash"),
        UniqueConstraint(
            "organization_id",
            "account_id",
            "candidate_id",
            "evaluation_revision",
            name="uq_action_eligibility_evaluations_lineage_revision",
        ),
        CheckConstraint(
            "evaluation_revision >= 1", name="action_eligibility_evaluations_revision_min"
        ),
        CheckConstraint(
            "length(uniqueness_hash) = 64",
            name="action_eligibility_evaluations_uniqueness_len",
        ),
        CheckConstraint(
            "length(content_hash) = 64",
            name="action_eligibility_evaluations_content_hash_len",
        ),
        Index(
            "ix_action_eligibility_evaluations_org_account_candidate",
            "organization_id",
            "account_id",
            "candidate_id",
            "evaluation_revision",
        ),
    )

    eligibility_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("canonical_candidates.candidate_id", name="fk_eligibility_candidate"),
        nullable=False,
    )
    candidate_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    uniqueness_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    paper_actionable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    live_executable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ActionEligibilityIdentityBindingRow(Base):
    __tablename__ = "action_eligibility_identity_bindings"
    __table_args__ = (
        CheckConstraint(
            "length(fingerprint) = 64",
            name="action_eligibility_identity_bindings_fingerprint_len",
        ),
    )

    binding_kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    binding_key: Mapped[str] = mapped_column(String(220), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


def _forbid_history_mutation(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    raise CanonicalEligibilityHistoryImmutabilityError(
        f"{type(target).__name__} rows are append-only and cannot be updated.",
        details={"model": type(target).__name__},
    )


def _forbid_history_delete(_mapper: Mapper[Any], _connection: Any, target: Any) -> None:
    raise CanonicalEligibilityHistoryImmutabilityError(
        f"{type(target).__name__} rows are append-only and cannot be deleted.",
        details={"model": type(target).__name__},
    )


def register_canonical_eligibility_immutability() -> None:
    global _registered
    if _registered:
        return
    for model in (ActionEligibilityEvaluationRow, ActionEligibilityIdentityBindingRow):
        event.listen(model, "before_update", _forbid_history_mutation)
        event.listen(model, "before_delete", _forbid_history_delete)
    _registered = True
