"""Explain recorded paper execution without evaluating, calculating or executing."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import ConversationMessage, ExecutionCommand, ExecutionFillFact
from app.interactive_agent.contracts import ArtifactKind, ConnectionRef, ProvenanceSource
from app.repositories.journal_trades import JournalTradeRepository
from app.runtime.canonical import build_production_canonical_runtime
from app.schemas.agent_paper import AgentPaperResult
from app.schemas.common import ConversationMessageRole
from app.services.canonical_reads import CanonicalReadService


@dataclass(frozen=True)
class ExecutionExplanation:
    reply: str
    connections: list[ConnectionRef]
    source_message_id: UUID


def read_paper_execution(
    session: Session,
    *,
    settings: Settings,
    organization_id: UUID,
    user_id: UUID,
    command_id: UUID,
) -> ExecutionExplanation:
    # Construct the same durable read authorities; no worker, evaluator, Risk
    # check, approval or execution method is invoked by this adapter.
    runtime = build_production_canonical_runtime(
        sessionmaker(bind=session.get_bind(), expire_on_commit=False), settings=settings
    )
    with session.no_autoflush, runtime.bind_session(session):
        command = session.scalar(
            select(ExecutionCommand).where(
                ExecutionCommand.id == command_id,
                ExecutionCommand.organization_id == organization_id,
                ExecutionCommand.user_id == user_id,
            )
        )
        if command is None:
            raise NotFoundError("Paper execution is unknown in this scope.")
        envelope = runtime.plans.get_scoped(
            command.revision_id, organization_id=organization_id, user_id=user_id
        )
        reads = CanonicalReadService(session, runtime)
        candidate = reads.get_candidate(
            organization_id=organization_id, candidate_id=envelope.lineage.candidate_id
        ).candidate
        receipt = reads.get_execution_receipt(
            organization_id=organization_id, receipt_id=command_id
        ).receipt
        journal = JournalTradeRepository(session).find_by_execution_lifecycle(
            organization_id=organization_id, execution_lifecycle_id=command_id
        )
        message = session.scalar(
            select(ConversationMessage)
            .where(
                ConversationMessage.organization_id == organization_id,
                ConversationMessage.user_id == user_id,
                ConversationMessage.role == ConversationMessageRole.ASSISTANT,
                ConversationMessage.payload["paper_execution"]["replayed"].as_boolean().is_(False),
                ConversationMessage.payload["paper_execution"]["paper_action_id"].as_string()
                == str(command_id),
            )
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
            .limit(1)
        )
        if message is None or journal is None or journal.user_id != user_id:
            raise NotFoundError("Recorded paper execution explanation is unavailable.")
        recorded = AgentPaperResult.model_validate(message.payload["paper_execution"])
        plan = envelope.plan
        if (
            recorded.stage != "executed"
            or recorded.plan.content_hash != plan.content_hash
            or recorded.plan.revision_id != command.revision_id
            or recorded.candidate_id != candidate.candidate_id
            or recorded.journal_trade_id != journal.id
            or recorded.eligibility_id != envelope.lineage.eligibility_id
            or recorded.receipt_id != receipt.receipt_id
            or recorded.authorization_id != command.authorization_id
            or command.plan_content_hash != plan.content_hash
        ):
            raise ValidationAppError("Recorded explanation lineage does not match execution.")
        fills = list(
            session.scalars(
                select(ExecutionFillFact)
                .where(
                    ExecutionFillFact.organization_id == organization_id,
                    ExecutionFillFact.command_id == command_id,
                )
                .order_by(ExecutionFillFact.occurred_at, ExecutionFillFact.id)
                .limit(10)
            )
        )
        lines = [
            f"Recorded internal paper execution {command.id}; outcome {receipt.outcome.value}.",
            f"Candidate {candidate.candidate_id}: "
            f"strategy version {candidate.strategy_version_id}, "
            f"compiled setup {candidate.setup_definition_id}, "
            f"assessment {candidate.assessment_id}, "
            f"evidence window {candidate.evidence_window_hash}.",
            f"ActionEligibility {recorded.eligibility_id}; approval authorization "
            f"{command.authorization_id} bound to this revision and hash.",
            f"Recorded Risk decision {recorded.risk_result.action.value}: "
            f"{recorded.risk_result.explanation}",
            f"TradePlan revision {plan.revision_id}; hash {plan.content_hash}; "
            f"{plan.side.value} {plan.execution_instrument}; entry "
            f"{plan.basis_policy.execution_price.value}; stop {plan.risk_and_exits.stop.value}; "
            f"quantity {plan.quantity.value}; "
            f"maximum loss {plan.risk_and_exits.maximum_loss.value}.",
            *[
                f"Paper fill {fill.id}: {fill.quantity} at {fill.price}; venue {fill.venue_source}."
                for fill in fills
            ],
            f"Journal {journal.id}: {journal.status.value}; recorded net PnL {journal.net_pnl}.",
            "Risk describes the captured execution decision. This read does not recalculate "
            "risk or PnL, confirm a proposal, execute an order or contact a provider. "
            "Fill references are limited to the first ten recorded fills.",
        ]
        references = [
            (candidate.candidate_id, "Candidate", ArtifactKind.TRADE_DECISION),
            (recorded.eligibility_id, "ActionEligibility", ArtifactKind.TRADE_DECISION),
            (plan.revision_id, "TradePlan revision", ArtifactKind.TRADE_DECISION),
            (command.id, "Paper execution command", ArtifactKind.TRADE_DECISION),
            (receipt.receipt_id, "Execution receipt", ArtifactKind.TRADE_DECISION),
            *[(fill.id, "Internal paper fill", ArtifactKind.TRADE_DECISION) for fill in fills],
            (journal.id, "Journal result", ArtifactKind.JOURNAL_ENTRY),
            (message.id, "Captured Risk and confirmation result", ArtifactKind.OBSERVATION),
        ]
        return ExecutionExplanation(
            reply="\n\n".join(lines)[:4000],
            source_message_id=message.id,
            connections=[
                ConnectionRef(
                    artifact_kind=kind,
                    record_id=str(identity),
                    title=title,
                    relation="recorded paper execution lineage",
                    provenance=ProvenanceSource.SYSTEM_GENERATED,
                )
                for identity, title, kind in references
            ],
        )
