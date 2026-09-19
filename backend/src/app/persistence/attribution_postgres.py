"""PostgreSQL adapter for AttributionStore.

Persists canonical learning attribution without becoming a JournalTrade writer.
Caller owns the unit of work. Duplicate source identity converges; conflicting
identity fails closed. Not wired into FastAPI, Watcher, Telegram, or execution.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.learning_attribution import (
    LearningAttributionEventRow,
    LearningAttributionRecordRow,
)
from app.learning_attribution.contracts import (
    AttributionEvent,
    AttributionFacts,
    AttributionRecord,
)
from app.learning_attribution.errors import LearningAttributionConflictError
from app.learning_attribution.identity import attribution_event_id_for
from app.persistence.unique import is_unique_violation
from app.schemas.common import JournalLifecycleEventType
from app.schemas.journal_lifecycle import JournalProjectionResult
from app.signal_fusion.types import hashed_model

_RECORD_UNIQUES = (
    "uq_learning_attribution_records_org_candidate",
    "pk_learning_attribution_records",
    "uq_learning_attribution_records_org_lifecycle",
)
_EVENT_UNIQUES = (
    "uq_learning_attribution_events_source",
    "pk_learning_attribution_events",
    "uq_learning_attribution_events_index",
)


class PostgresAttributionStore:
    """Durable AttributionStore. In-memory remains the unit-test default."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, *, organization_id: UUID, candidate_id: UUID) -> AttributionRecord | None:
        row = self._session.scalars(
            select(LearningAttributionRecordRow).where(
                LearningAttributionRecordRow.organization_id == organization_id,
                LearningAttributionRecordRow.candidate_id == candidate_id,
            )
        ).first()
        if row is None:
            return None
        return self._record_from_row(row)

    def get_by_lifecycle(
        self,
        *,
        organization_id: UUID,
        execution_lifecycle_id: UUID,
    ) -> AttributionRecord | None:
        row = self._session.scalars(
            select(LearningAttributionRecordRow).where(
                LearningAttributionRecordRow.organization_id == organization_id,
                LearningAttributionRecordRow.execution_lifecycle_id == execution_lifecycle_id,
            )
        ).first()
        if row is None:
            return None
        return self._record_from_row(row)

    def find_event(
        self,
        *,
        organization_id: UUID,
        source_system: str,
        source_aggregate: str,
        event_type: str,
        source_event_id: str,
        source_event_version: int,
        supersession: int,
        account_id: UUID,
    ) -> AttributionEvent | None:
        row = self._find_event_row(
            organization_id=organization_id,
            account_id=account_id,
            source_system=source_system,
            source_aggregate=source_aggregate,
            event_type=event_type,
            source_event_id=source_event_id,
            source_event_version=source_event_version,
            supersession=supersession,
        )
        return None if row is None else _event_from_row(row)

    def put(self, record: AttributionRecord) -> None:
        if record.facts.organization_id != record.organization_id:
            raise LearningAttributionConflictError(
                "Attribution facts organization does not match the record.",
                details={"reason": "cross_tenant_attribution"},
            )
        row = self._lock_record(record.organization_id, record.candidate_id)
        if row is None:
            _assert_lifecycle_owner(self._session, record)
            try:
                with self._session.begin_nested():
                    row = _new_record_row(record)
                    self._session.add(row)
                    self._session.flush()
            except IntegrityError as exc:
                if not is_unique_violation(exc, *_RECORD_UNIQUES):
                    raise
                row = self._lock_record(record.organization_id, record.candidate_id)
                if row is None:
                    raise LearningAttributionConflictError(
                        "Execution lifecycle is already bound to a different candidate.",
                        details={
                            "reason": "lifecycle_candidate_conflict",
                            "execution_lifecycle_id": str(record.execution_lifecycle_id),
                        },
                    ) from exc
                _assert_row_identity(row, record)
                _apply_record_projection(row, record)
        else:
            _assert_row_identity(row, record)
            _assert_lifecycle_owner(self._session, record)
            _apply_record_projection(row, record)
        self._insert_events(record)
        self._session.flush()

    def list_for_organization(self, organization_id: UUID) -> tuple[AttributionRecord, ...]:
        rows = self._session.scalars(
            select(LearningAttributionRecordRow)
            .where(LearningAttributionRecordRow.organization_id == organization_id)
            .order_by(LearningAttributionRecordRow.candidate_id)
        ).all()
        return tuple(self._record_from_row(row) for row in rows)

    def _lock_record(
        self, organization_id: UUID, candidate_id: UUID
    ) -> LearningAttributionRecordRow | None:
        return self._session.scalars(
            select(LearningAttributionRecordRow)
            .where(
                LearningAttributionRecordRow.organization_id == organization_id,
                LearningAttributionRecordRow.candidate_id == candidate_id,
            )
            .with_for_update()
        ).first()

    def _find_event_row(
        self,
        *,
        organization_id: UUID,
        account_id: UUID,
        source_system: str,
        source_aggregate: str,
        event_type: str,
        source_event_id: str,
        source_event_version: int,
        supersession: int,
    ) -> LearningAttributionEventRow | None:
        return self._session.scalars(
            select(LearningAttributionEventRow).where(
                LearningAttributionEventRow.organization_id == organization_id,
                LearningAttributionEventRow.account_id == account_id,
                LearningAttributionEventRow.source_system == source_system,
                LearningAttributionEventRow.source_aggregate == source_aggregate,
                LearningAttributionEventRow.event_type == event_type,
                LearningAttributionEventRow.source_event_id == source_event_id,
                LearningAttributionEventRow.source_event_version == source_event_version,
                LearningAttributionEventRow.supersession == supersession,
            )
        ).first()

    def _insert_events(self, record: AttributionRecord) -> None:
        existing = self._session.scalars(
            select(LearningAttributionEventRow)
            .where(
                LearningAttributionEventRow.organization_id == record.organization_id,
                LearningAttributionEventRow.attribution_id == record.attribution_id,
            )
            .order_by(LearningAttributionEventRow.event_index)
        ).all()
        known = {_event_identity(row): row for row in existing}
        next_index = max((row.event_index for row in existing), default=0)
        lineage = _payload_lineage(record)
        for event in record.events:
            event_type = _event_type_value(event.event_type)
            identity = (
                record.organization_id,
                record.facts.account_id,
                event.source_system,
                event.source_aggregate,
                event_type,
                event.source_event_id,
                event.source_event_version,
                event.supersession,
            )
            prior = known.get(identity)
            if prior is not None:
                if prior.event_content_hash != event.event_content_hash:
                    raise LearningAttributionConflictError(
                        "Attribution source identity replayed with conflicting content.",
                        details={"reason": "conflicting_source_identity"},
                    )
                continue
            next_index += 1
            row = LearningAttributionEventRow(
                id=attribution_event_id_for(
                    organization_id=record.organization_id,
                    account_id=record.facts.account_id,
                    source_system=event.source_system,
                    source_aggregate=event.source_aggregate,
                    event_type=event_type,
                    source_event_id=event.source_event_id,
                    source_event_version=event.source_event_version,
                    supersession=event.supersession,
                ),
                attribution_id=record.attribution_id,
                organization_id=record.organization_id,
                account_id=record.facts.account_id,
                event_index=next_index,
                event_type=event_type,
                source_system=event.source_system,
                source_aggregate=event.source_aggregate,
                source_event_id=event.source_event_id,
                source_event_version=event.source_event_version,
                supersession=event.supersession,
                event_content_hash=event.event_content_hash,
                facts_hash=event.facts_hash,
                journal_trade_id=event.journal_trade_id,
                payload_lineage=lineage,
                projection=event.projection.model_dump(mode="json"),
                narrative_explanation=event.narrative_explanation,
                created_at=datetime.now(UTC),
            )
            try:
                with self._session.begin_nested():
                    self._session.add(row)
                    self._session.flush()
            except IntegrityError as exc:
                if not is_unique_violation(exc, *_EVENT_UNIQUES):
                    raise
                winner = self._find_event_row(
                    organization_id=record.organization_id,
                    account_id=record.facts.account_id,
                    source_system=event.source_system,
                    source_aggregate=event.source_aggregate,
                    event_type=event_type,
                    source_event_id=event.source_event_id,
                    source_event_version=event.source_event_version,
                    supersession=event.supersession,
                )
                if winner is None:
                    raise
                if winner.event_content_hash != event.event_content_hash:
                    raise LearningAttributionConflictError(
                        "Attribution source identity replayed with conflicting content.",
                        details={"reason": "conflicting_source_identity"},
                    ) from exc
            known[identity] = row

    def _record_from_row(self, row: LearningAttributionRecordRow) -> AttributionRecord:
        events = self._session.scalars(
            select(LearningAttributionEventRow)
            .where(
                LearningAttributionEventRow.organization_id == row.organization_id,
                LearningAttributionEventRow.attribution_id == row.id,
            )
            .order_by(LearningAttributionEventRow.event_index)
        ).all()
        facts = _facts_from_payload(row.facts_payload, expected_hash=row.facts_hash)
        return AttributionRecord(
            attribution_id=row.id,
            organization_id=row.organization_id,
            candidate_id=row.candidate_id,
            execution_lifecycle_id=row.execution_lifecycle_id,
            journal_trade_id=row.journal_trade_id,
            facts=facts,
            events=tuple(_event_from_row(item) for item in events),
            narrative_explanation=row.narrative_explanation,
        )


def _assert_lifecycle_owner(session: Session, record: AttributionRecord) -> None:
    lifecycle_id = record.execution_lifecycle_id
    if lifecycle_id is None:
        return
    owner = session.scalars(
        select(LearningAttributionRecordRow).where(
            LearningAttributionRecordRow.organization_id == record.organization_id,
            LearningAttributionRecordRow.execution_lifecycle_id == lifecycle_id,
        )
    ).first()
    if owner is not None and owner.candidate_id != record.candidate_id:
        raise LearningAttributionConflictError(
            "Execution lifecycle is already bound to a different candidate.",
            details={
                "reason": "lifecycle_candidate_conflict",
                "execution_lifecycle_id": str(lifecycle_id),
            },
        )


def _assert_row_identity(row: LearningAttributionRecordRow, record: AttributionRecord) -> None:
    if row.organization_id != record.organization_id:
        raise LearningAttributionConflictError(
            "Attribution record belongs to a different organization.",
            details={"reason": "cross_tenant_attribution"},
        )
    if row.candidate_id != record.candidate_id:
        raise LearningAttributionConflictError(
            "Attribution candidate identity conflict.",
            details={"reason": "candidate_identity_conflict"},
        )
    if row.assessment_id != record.facts.assessment_id:
        raise LearningAttributionConflictError(
            "SetupAssessment identity conflict for this attribution aggregate.",
            details={"reason": "assessment_identity_conflict"},
        )
    if row.evidence_window_hash != record.facts.evidence_window_hash:
        raise LearningAttributionConflictError(
            "Evidence window hash conflict for this attribution aggregate.",
            details={"reason": "evidence_window_conflict"},
        )
    if row.uniqueness_tuple_hash != record.facts.uniqueness_tuple_hash:
        raise LearningAttributionConflictError(
            "Candidate uniqueness tuple conflict for this attribution aggregate.",
            details={"reason": "uniqueness_tuple_conflict"},
        )
    if row.learning_venue_mode != record.facts.learning_venue_mode.value:
        raise LearningAttributionConflictError(
            "Learning venue mode conflict for this attribution aggregate.",
            details={"reason": "learning_venue_mode_conflict"},
        )
    if (
        row.execution_lifecycle_id is not None
        and record.execution_lifecycle_id is not None
        and row.execution_lifecycle_id != record.execution_lifecycle_id
    ):
        raise LearningAttributionConflictError(
            "Candidate is already bound to a different execution lifecycle.",
            details={"reason": "candidate_lifecycle_conflict"},
        )


def _apply_record_projection(row: LearningAttributionRecordRow, record: AttributionRecord) -> None:
    facts = record.facts
    pattern = facts.strategy_pattern
    row.user_id = facts.user_id
    row.account_id = facts.account_id
    row.candidate_content_hash = facts.candidate_content_hash
    if row.execution_lifecycle_id is None:
        row.execution_lifecycle_id = record.execution_lifecycle_id
    if row.journal_trade_id is None:
        row.journal_trade_id = record.journal_trade_id
    if row.trade_plan_revision_id is None:
        row.trade_plan_revision_id = facts.trade_plan_revision_id
    row.facts_hash = facts.content_hash
    row.executed_trade_outcome = facts.outcome.eligible
    row.setup_quality_axis = facts.setup_quality.axis.value
    row.execution_quality_axis = facts.execution_quality.axis.value
    row.risk_adherence_axis = facts.risk_adherence.axis.value
    row.trader_behavior_axis = facts.trader_behavior.axis.value
    row.decision_actor = facts.trader_behavior.actor.value
    row.strategy_version_id = pattern.strategy_version_id
    row.setup_definition_id = pattern.setup_definition_id
    row.fusion_policy_version = pattern.fusion_policy_version
    row.rejected = pattern.rejected
    row.skipped = pattern.skipped
    row.plan_approved = pattern.plan_approved
    row.filled = pattern.filled
    row.closed = pattern.closed
    row.win = pattern.win
    row.loss = pattern.loss
    row.breakeven = pattern.breakeven
    row.facts_payload = facts.model_dump(mode="json")
    row.narrative_explanation = record.narrative_explanation


def _new_record_row(record: AttributionRecord) -> LearningAttributionRecordRow:
    facts = record.facts
    pattern = facts.strategy_pattern
    return LearningAttributionRecordRow(
        id=record.attribution_id,
        organization_id=record.organization_id,
        user_id=facts.user_id,
        account_id=facts.account_id,
        candidate_id=record.candidate_id,
        assessment_id=facts.assessment_id,
        evidence_window_hash=facts.evidence_window_hash,
        uniqueness_tuple_hash=facts.uniqueness_tuple_hash,
        candidate_content_hash=facts.candidate_content_hash,
        execution_lifecycle_id=record.execution_lifecycle_id,
        journal_trade_id=record.journal_trade_id,
        trade_plan_revision_id=facts.trade_plan_revision_id,
        facts_hash=facts.content_hash,
        executed_trade_outcome=facts.outcome.eligible,
        learning_venue_mode=facts.learning_venue_mode.value,
        setup_quality_axis=facts.setup_quality.axis.value,
        execution_quality_axis=facts.execution_quality.axis.value,
        risk_adherence_axis=facts.risk_adherence.axis.value,
        trader_behavior_axis=facts.trader_behavior.axis.value,
        decision_actor=facts.trader_behavior.actor.value,
        strategy_version_id=pattern.strategy_version_id,
        setup_definition_id=pattern.setup_definition_id,
        fusion_policy_version=pattern.fusion_policy_version,
        rejected=pattern.rejected,
        skipped=pattern.skipped,
        plan_approved=pattern.plan_approved,
        filled=pattern.filled,
        closed=pattern.closed,
        win=pattern.win,
        loss=pattern.loss,
        breakeven=pattern.breakeven,
        facts_payload=facts.model_dump(mode="json"),
        narrative_explanation=record.narrative_explanation,
    )


def _facts_from_payload(payload: dict[str, object], *, expected_hash: str) -> AttributionFacts:
    loaded = AttributionFacts.model_validate(payload)
    recomputed = hashed_model(loaded.model_copy(update={"content_hash": "0" * 64}))
    if recomputed.content_hash != expected_hash or loaded.content_hash != expected_hash:
        raise LearningAttributionConflictError(
            "Persisted attribution facts hash does not match canonical facts.",
            details={"reason": "persisted_facts_hash_mismatch"},
        )
    return loaded


def _event_from_row(row: LearningAttributionEventRow) -> AttributionEvent:
    return AttributionEvent(
        event_type=JournalLifecycleEventType(row.event_type),
        source_system=row.source_system,
        source_aggregate=row.source_aggregate,
        source_event_id=row.source_event_id,
        source_event_version=row.source_event_version,
        supersession=row.supersession,
        event_content_hash=row.event_content_hash,
        facts_hash=row.facts_hash,
        journal_trade_id=row.journal_trade_id,
        projection=JournalProjectionResult.model_validate(row.projection),
        narrative_explanation=row.narrative_explanation,
    )


def _event_type_value(event_type: JournalLifecycleEventType | str) -> str:
    if isinstance(event_type, JournalLifecycleEventType):
        return event_type.value
    return str(event_type)


def _event_identity(row: LearningAttributionEventRow) -> tuple[object, ...]:
    return (
        row.organization_id,
        row.account_id,
        row.source_system,
        row.source_aggregate,
        row.event_type,
        row.source_event_id,
        row.source_event_version,
        row.supersession,
    )


def _payload_lineage(record: AttributionRecord) -> dict[str, object]:
    facts = record.facts
    payload: dict[str, Any] = {
        "organization_id": str(facts.organization_id),
        "account_id": str(facts.account_id),
        "candidate_id": str(facts.candidate_id),
        "candidate_content_hash": facts.candidate_content_hash,
        "assessment_id": str(facts.assessment_id),
        "evidence_window_hash": facts.evidence_window_hash,
        "uniqueness_tuple_hash": facts.uniqueness_tuple_hash,
        "setup_definition_id": str(facts.strategy_pattern.setup_definition_id),
        "strategy_version_id": str(facts.strategy_pattern.strategy_version_id),
        "fusion_policy_version": facts.strategy_pattern.fusion_policy_version,
        "learning_venue_mode": facts.learning_venue_mode.value,
    }
    if facts.execution_lifecycle_id is not None:
        payload["execution_lifecycle_id"] = str(facts.execution_lifecycle_id)
    if facts.trade_plan_revision_id is not None:
        payload["trade_plan_revision_id"] = str(facts.trade_plan_revision_id)
    return payload
