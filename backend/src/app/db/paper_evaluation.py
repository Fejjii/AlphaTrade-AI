"""ORM for durable paper-evaluation observations.

Append-only measurement facts. Duplicate source identity converges.
This table is not a JournalTrade writer and does not mint Candidates.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.errors import ConflictError, ValidationAppError
from app.db.base import Base, TimestampMixin

_registered = False

_IDENTITY_ATTRS = (
    "organization_id",
    "source_system",
    "source_event_id",
    "source_event_version",
    "content_hash",
    "stage",
)


class PaperEvaluationHistoryImmutabilityError(ValidationAppError):
    code = "paper_evaluation_history_immutable"


class PaperEvaluationIdentityMutationError(ConflictError):
    code = "paper_evaluation_identity_immutable"


class PaperEvaluationObservationRow(TimestampMixin, Base):
    __tablename__ = "paper_evaluation_observations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "source_system",
            "source_event_id",
            "source_event_version",
            name="uq_paper_evaluation_observations_source",
        ),
        UniqueConstraint(
            "organization_id",
            "observation_id",
            name="uq_paper_evaluation_observations_org_id",
        ),
        CheckConstraint(
            "length(content_hash) = 64",
            name="paper_evaluation_observations_hash_len",
        ),
        CheckConstraint(
            "source_event_version >= 1",
            name="paper_evaluation_observations_version_min",
        ),
        Index(
            "ix_paper_evaluation_observations_org_stage",
            "organization_id",
            "stage",
            "occurred_at",
        ),
        Index(
            "ix_paper_evaluation_observations_org_candidate",
            "organization_id",
            "candidate_id",
        ),
    )

    observation_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    source_event_version: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    strategy_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    setup_definition_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    journal_trade_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    scan_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    assessment_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    eligibility_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_quality: Mapped[str] = mapped_column(String(32), nullable=False)
    replayed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    plan_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rejected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    executed_outcome: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    net_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    mfe_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    mae_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    capture_pct: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    planned_risk_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    setup_quality: Mapped[str | None] = mapped_column(String(32), nullable=True)
    execution_quality: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_adherence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trader_behavior: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rule_compliance: Mapped[str | None] = mapped_column(String(32), nullable=True)
    learning_venue_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    live_executable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    narrative_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


def register_paper_evaluation_immutability() -> None:
    """Identity columns cannot be rewritten; narrative may be attached later."""

    global _registered
    if _registered:
        return

    @event.listens_for(PaperEvaluationObservationRow, "before_update")
    def _forbid_identity(
        mapper: object,
        connection: object,
        target: PaperEvaluationObservationRow,
    ) -> None:
        from sqlalchemy import inspect as sa_inspect

        _ = mapper, connection
        state = sa_inspect(target)
        for attr in _IDENTITY_ATTRS:
            history = state.attrs[attr].history
            if history.has_changes():
                raise PaperEvaluationIdentityMutationError(
                    "Paper evaluation identity columns cannot be rewritten."
                )

    _registered = True
