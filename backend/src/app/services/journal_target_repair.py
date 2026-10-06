"""Read-only validation for a single canonical Journal target projection repair."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import JournalProjectionConflictError
from app.db.models import (
    ApprovalAuthorization,
    ExecutionCommand,
    JournalLifecycleEvent,
    JournalTrade,
)
from app.persistence.trade_plan_postgres import PostgresCanonicalTradePlanStore
from app.schemas.canonical_trade_plan import CanonicalTradePlanRevision
from app.schemas.common import JournalLifecycleEventType, JournalTradeSource
from app.schemas.execution_protocol import ExecutionCommandOutcome
from app.schemas.trade_plan import AuthorizationState, ExecutionMode, TradePlanRevisionSemantic
from app.services.canonical_execution_journal import CANONICAL_EXECUTION_SOURCE_SYSTEM
from app.services.canonical_serialization import canonical_sha256
from app.services.journal_lifecycle_lineage import extract_lineage_map


def approved_plan_for_target_repair(
    session: Session, trade: JournalTrade, *, revision_id: UUID
) -> CanonicalTradePlanRevision:
    """Require plan, consumed authorization, command and immutable Journal lineage."""

    def require(condition: bool) -> None:
        if not condition:
            raise JournalProjectionConflictError("Journal target repair lineage does not match.")

    require(trade.source is JournalTradeSource.PAPER_EXECUTION)
    require(trade.execution_lifecycle_id is not None)
    store = PostgresCanonicalTradePlanStore(sessionmaker(bind=session.get_bind()))
    with store.bind_session(session):
        envelope = store.get_by_revision(
            organization_id=trade.organization_id, user_id=trade.user_id, revision_id=revision_id
        )
    require(envelope is not None)
    assert envelope is not None
    plan = envelope.plan
    semantic = TradePlanRevisionSemantic.model_validate(
        plan.model_dump(
            exclude={"correlation_id", "content_hash", "created_at", "presentation_metadata"}
        )
    )
    require(canonical_sha256(semantic) == plan.content_hash)
    require(
        canonical_sha256(
            {
                "lineage": envelope.lineage.model_dump(mode="python"),
                "plan_content_hash": plan.content_hash,
                "uniqueness_hash": envelope.uniqueness_hash,
            }
        )
        == envelope.content_hash
    )
    require(
        (plan.organization_id, plan.user_id, plan.account_id, plan.revision_id)
        == (trade.organization_id, trade.user_id, trade.account_id, revision_id)
    )
    require(
        (
            trade.trade_plan_revision_id,
            trade.linked_proposal_id,
            trade.strategy_version_id,
            trade.candidate_id,
            trade.assessment_id,
            trade.evidence_window_hash,
        )
        == (
            revision_id,
            plan.plan_id,
            plan.strategy_version_id,
            envelope.lineage.candidate_id,
            envelope.lineage.assessment_id,
            envelope.lineage.evidence_window_hash,
        )
    )
    command = session.scalar(
        select(ExecutionCommand).where(
            ExecutionCommand.id == trade.execution_lifecycle_id,
            ExecutionCommand.organization_id == trade.organization_id,
            ExecutionCommand.user_id == trade.user_id,
            ExecutionCommand.account_id == trade.account_id,
        )
    )
    require(command is not None)
    assert command is not None
    require(command.outcome is ExecutionCommandOutcome.ALLOW)
    require(
        (command.revision_id, command.plan_id, command.plan_content_hash)
        == (revision_id, plan.plan_id, plan.content_hash)
    )
    approval = session.scalar(
        select(ApprovalAuthorization).where(
            ApprovalAuthorization.id == command.authorization_id,
            ApprovalAuthorization.organization_id == trade.organization_id,
            ApprovalAuthorization.user_id == trade.user_id,
            ApprovalAuthorization.account_id == trade.account_id,
        )
    )
    require(approval is not None)
    assert approval is not None
    require(approval.execution_mode is ExecutionMode.PAPER)
    require(approval.state is AuthorizationState.CONSUMED)
    require(approval.consumed_by_execution_command_id == command.id)
    require(
        (approval.revision_id, approval.plan_id, approval.plan_content_hash)
        == (revision_id, plan.plan_id, plan.content_hash)
    )
    rows = list(
        session.scalars(
            select(JournalLifecycleEvent).where(
                JournalLifecycleEvent.organization_id == trade.organization_id,
                JournalLifecycleEvent.execution_lifecycle_id == command.id,
            )
        )
    )
    require(bool(rows))
    require(
        any(
            row.event_type
            in {JournalLifecycleEventType.APPROVED_PLAN, JournalLifecycleEventType.FILL}
            for row in rows
        )
    )
    expected = {
        "organization_id": str(trade.organization_id),
        "account_id": str(trade.account_id),
        "execution_lifecycle_id": str(command.id),
        "trade_plan_revision_id": str(revision_id),
        "trade_plan_content_hash": plan.content_hash,
        "candidate_id": str(envelope.lineage.candidate_id),
        "assessment_id": str(envelope.lineage.assessment_id),
        "candidate_content_hash": envelope.lineage.candidate_content_hash,
        "evidence_window_hash": envelope.lineage.evidence_window_hash,
        "strategy_version_id": str(envelope.lineage.strategy_version_id),
        "setup_definition_id": str(envelope.lineage.setup_definition_id),
        "fusion_policy_version": envelope.lineage.fusion_policy_version,
        "uniqueness_tuple_hash": envelope.uniqueness_hash,
    }
    for row in rows:
        require(row.user_id == trade.user_id and row.account_id == trade.account_id)
        require(row.journal_trade_id == trade.id)
        require(row.source_system == CANONICAL_EXECUTION_SOURCE_SYSTEM)
        require(row.source_aggregate == "execution-command")
        lineage = extract_lineage_map(row.payload)
        require(all(lineage.get(key) == value for key, value in expected.items()))
    return envelope
