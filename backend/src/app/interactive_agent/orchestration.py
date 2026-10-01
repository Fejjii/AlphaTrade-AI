"""Adapters to existing domain authorities; proposals share the existing transcript store."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, TradingPolicyError, ValidationAppError
from app.db.models import Conversation, Document, TradeJournal
from app.interactive_agent.action_registry import Tool, resolve_action
from app.interactive_agent.actions import (
    ActionRequest,
    JournalCreateInput,
    JournalNoteInput,
    KnowledgeInput,
    PaperTradeInput,
    StrategyInput,
    WatcherChangeInput,
)
from app.interactive_agent.contracts import (
    ArtifactKind,
    ProposalLifecycle,
    ProvenanceSource,
    StructuredActionProposal,
)
from app.interactive_agent.proposals import build_proposal, parse_journal_draft
from app.repositories.strategy_library import UserStrategyRepository
from app.repositories.watcher_watchlist import WatcherWatchlistRepository
from app.schemas.common import DocumentSourceType, RiskAction, StrictModel
from app.schemas.journal import JournalEntryUpdate
from app.schemas.rag import IngestDocumentRequest
from app.schemas.watcher_watchlist import WatcherWatchlistReplace
from app.services.audit_service import AuditService
from app.services.canonical_serialization import canonical_sha256
from app.services.journal_service import JournalService
from app.services.proposal_service import ProposalService
from app.services.strategy_proposal_service import StrategyProposalService
from app.workers.watcher_watchlist import (
    WatchlistValidationError,
    reorder_slots,
    replace_symbol,
    replace_watchlist,
    set_enabled,
)


def propose_action(
    session: Session,
    *,
    tool: Tool,
    inputs: StrictModel,
    conversation: Conversation,
    source_message_id: UUID,
) -> StructuredActionProposal:
    """Draft one action, with no application or execution permission."""
    linked: UUID | None = None
    artifact = tool.artifact
    payload: dict[str, Any] = {}
    missing: list[str] = []
    if isinstance(inputs, JournalCreateInput):
        draft = parse_journal_draft(inputs.text)
        for field in ("symbol", "timeframe", "direction"):
            value = getattr(inputs, field)
            if value is not None:
                setattr(draft, field, str(value))
        draft.incomplete_fields = [
            field for field in ("symbol", "timeframe", "direction") if not getattr(draft, field)
        ]
        payload["journal"] = draft.model_dump(mode="json")
        missing = draft.incomplete_fields
    elif isinstance(inputs, JournalNoteInput):
        if inputs.journal_entry_id is None:
            missing = ["journal_entry_id"]
        else:
            row = require_journal(session, inputs.journal_entry_id, conversation)
            payload["journal_snapshot_hash"] = journal_snapshot_hash(row)
        payload["journal_entry_id"] = (
            str(inputs.journal_entry_id) if inputs.journal_entry_id else None
        )
        payload["text"] = inputs.text
    elif isinstance(inputs, StrategyInput):
        target = inputs.strategy_id or conversation.strategy_id
        evidence = _require_refs(session, conversation, target, inputs.evidence_document_ids)
        payload.update(
            {
                "text": inputs.text,
                "strategy_id": str(target) if target else None,
                "evidence_document_ids": evidence,
                "evidence_associated": False,
            }
        )
        if isinstance(inputs, KnowledgeInput):
            artifact = ArtifactKind(inputs.kind)
            ingest = IngestDocumentRequest(
                organization_id=conversation.organization_id,
                user_id=conversation.user_id,
                source_type=DocumentSourceType.TRADING_PLAYBOOK
                if inputs.kind == "rule"
                else DocumentSourceType.GENERAL_NOTE,
                title=inputs.title,
                text=inputs.text,
                strategy_tag=str(target) if target else None,
            )
            payload["ingest_request"] = ingest.model_dump(mode="json")
            payload["handoff"] = {"method": "POST", "path": "/knowledge/ingest"}
            payload["ingested"] = False
        elif tool.name in {"strategy.create", "strategy.refinement"}:
            payload.update(
                {
                    "compiled": False,
                    "approved": False,
                    "mutates_strategy_authority": False,
                    "linked_preview_stored": False,
                }
            )
            if tool.name == "strategy.refinement" and target is None:
                missing = ["strategy_id"]
            else:
                record = StrategyProposalService(session).create_draft_from_text(
                    conversation,
                    text=inputs.text,
                    strategy_id=target,
                    source_message_id=source_message_id,
                    context_refs={"agent_action": tool.name, "evidence_document_ids": evidence},
                )
                linked = record.id
                payload["linked_preview_stored"] = True
                payload["strategy_preview_hash"] = record.content_hash
                payload["handoff"] = {
                    "method": "POST",
                    "path": f"/conversations/{conversation.id}/proposals/{linked}/confirm",
                }
        elif tool.name == "strategy.associate_evidence":
            missing = (["strategy_id"] if target is None else []) + (
                ["evidence_document_ids"] if not evidence else []
            )
        elif tool.name == "strategy.request_validation":
            missing = ["strategy_id"] if target is None else []
            payload.update({"validation_ran": False, "replay_ran": False, "scheduled": False})
    elif isinstance(inputs, WatcherChangeInput):
        payload, missing = _watcher_preview(session, conversation.organization_id, inputs)
    elif isinstance(inputs, PaperTradeInput):
        payload = _paper_preview(session, conversation, inputs)
        missing = [
            key
            for key in ("symbol", "timeframe", "direction", "entry", "stop", "targets")
            if not payload.get(key)
        ]
    else:
        raise ValidationAppError("Action has no proposal adapter.")
    payload["missing_fields"] = missing
    payload["action"] = tool.descriptor().model_dump(exclude={"input_contract"})
    payload["action_input"] = inputs.model_dump(mode="json")
    summary = f"{tool.name} proposal. "
    summary += f"Missing fields: {', '.join(missing)}." if missing else "Ready for explicit review."
    if tool.name == "paper_trade.propose":
        summary += f" Risk: {payload['risk_state']}. No execution permission."
    return build_proposal(
        conversation_id=conversation.id,
        organization_id=conversation.organization_id,
        user_id=conversation.user_id,
        kind=tool.kind,
        artifact_kind=artifact,
        provenance=ProvenanceSource.USER_SUPPLIED,
        status=ProposalLifecycle.PROPOSED,
        summary=summary,
        payload=payload,
        authority=tool.authority,
        linked_strategy_proposal_id=linked,
    )


def _require_refs(
    session: Session,
    conversation: Conversation,
    strategy_id: UUID | None,
    documents: list[UUID],
) -> list[str]:
    if (
        strategy_id is not None
        and UserStrategyRepository(session).get_scoped(
            strategy_id,
            organization_id=conversation.organization_id,
            user_id=conversation.user_id,
        )
        is None
    ):
        raise NotFoundError("Strategy not found.")
    for record_id in documents:
        row = session.scalar(
            select(Document).where(
                Document.id == record_id,
                Document.organization_id == conversation.organization_id,
                or_(Document.user_id == conversation.user_id, Document.user_id.is_(None)),
            )
        )
        if row is None:
            raise NotFoundError("Evidence document not found.")
    return [str(record_id) for record_id in dict.fromkeys(documents)]


def require_journal(
    session: Session,
    entry_id: UUID,
    conversation: Conversation,
    *,
    lock: bool = False,
) -> TradeJournal:
    stmt = (
        select(TradeJournal)
        .where(
            TradeJournal.id == entry_id,
            TradeJournal.organization_id == conversation.organization_id,
            TradeJournal.user_id == conversation.user_id,
        )
        .execution_options(populate_existing=True)
    )
    if lock:
        stmt = stmt.with_for_update()
    row = session.scalar(stmt)
    if row is None:
        raise NotFoundError("Journal entry not found.")
    return row


def journal_snapshot_hash(row: TradeJournal) -> str:
    return canonical_sha256(
        {
            "id": row.id,
            "lessons": row.lessons,
            "mistakes": row.mistakes,
            "tags": row.tags,
        }
    )


def _watcher_preview(
    session: Session,
    organization_id: UUID,
    inputs: WatcherChangeInput,
) -> tuple[dict[str, Any], list[str]]:
    current = WatcherWatchlistRepository(session).load(organization_id)
    if inputs.revision is not None and inputs.revision != current.revision:
        raise ConflictError("Watchlist changed; reload before proposing.")
    position = inputs.position
    if position is None and inputs.symbol and inputs.operation in {"enable", "disable"}:
        position = next((s.position for s in current.slots if s.symbol == inputs.symbol), None)
    missing: list[str] = []
    preview = None
    try:
        if inputs.operation in {"enable", "disable", "replace"}:
            if position is None:
                missing.append("position")
            elif inputs.operation == "replace":
                if inputs.symbol is None:
                    missing.append("symbol")
                else:
                    preview = replace_symbol(current, position, inputs.symbol)
            else:
                preview = set_enabled(current, position, inputs.operation == "enable")
        elif inputs.operation == "reorder":
            if not inputs.positions:
                missing.append("positions")
            else:
                preview = reorder_slots(current, inputs.positions)
        elif not inputs.slots:
            missing.append("slots")
        else:
            preview = replace_watchlist([(s.symbol, s.enabled) for s in inputs.slots])
    except WatchlistValidationError as exc:
        raise ValidationAppError(str(exc)) from exc
    replacement = None
    if preview is not None:
        replacement = WatcherWatchlistReplace(
            revision=current.revision,
            slots=[{"symbol": s.symbol, "enabled": s.enabled} for s in preview.slots],
        ).model_dump(mode="json")
    return {
        "operation": inputs.operation,
        "configuration_revision": current.revision,
        "current_slots": [asdict(s) for s in current.slots],
        "replace_request": replacement,
        "validation_passed": preview is not None,
        "handoff": {"method": "PUT", "path": "/watcher/watchlist"},
        "configuration_changed": False,
    }, missing


def _paper_preview(
    session: Session,
    conversation: Conversation,
    inputs: PaperTradeInput,
) -> dict[str, Any]:
    payload: dict[str, Any] = inputs.model_dump(mode="json")
    payload.update(
        {
            "risk_state": "not_assessed",
            "risk_result": None,
            "executable": False,
            "execution_attempted": False,
            "candidate_minted": False,
            "sizing_performed": False,
            "handoff": {"method": "POST", "path": "/pretrade/analyze"},
        }
    )
    if inputs.trade_proposal_id is not None:
        proposal = ProposalService(session, AuditService(session)).get(
            inputs.trade_proposal_id,
            organization_id=conversation.organization_id,
            user_id=conversation.user_id,
        )
        payload.update(
            {
                "symbol": str(proposal.symbol),
                "timeframe": proposal.timeframe.value,
                "direction": proposal.direction.value,
                "entry": str(proposal.entry_price),
                "stop": str(proposal.exit.stop_loss),
                "targets": [str(tp.price) for tp in proposal.exit.take_profits],
                "invalidation": proposal.exit.invalidation,
                "risk_state": proposal.risk_result.action.value
                if proposal.risk_result
                else "not_assessed",
                "risk_result": proposal.risk_result.model_dump(mode="json")
                if proposal.risk_result
                else None,
                "approval_required": proposal.approval_required,
                "loss_acceptance_status": proposal.loss_acceptance_status.value,
                "proposal_status": proposal.status.value,
                "handoff": {"method": "GET", "path": f"/proposals/{proposal.id}/workflow"},
            }
        )
    return payload


def check_action_confirmation(
    session: Session,
    proposal: StructuredActionProposal,
    conversation: Conversation,
) -> tuple[Tool, StrictModel] | None:
    """Revalidate current scoped authorities after the existing hash/row-lock boundary."""
    raw = proposal.payload.get("action")
    if raw is None:
        return None  # Existing v1 proposals retain their original behavior.
    if not isinstance(raw, dict):
        raise ValidationAppError("Stored action descriptor is invalid.")
    tool, inputs = resolve_action(
        ActionRequest(
            name=raw.get("name", ""),
            arguments=proposal.payload.get("action_input", {}),
        )
    )
    if (
        raw != tool.descriptor().model_dump(exclude={"input_contract"})
        or proposal.kind != tool.kind
        or proposal.authority != tool.authority
    ):
        raise ConflictError("Stored action contract does not match its authority.")
    if isinstance(inputs, StrategyInput):
        _require_refs(
            session,
            conversation,
            inputs.strategy_id or conversation.strategy_id,
            inputs.evidence_document_ids,
        )
    if isinstance(inputs, WatcherChangeInput):
        current = WatcherWatchlistRepository(session).load(conversation.organization_id)
        if current.revision != proposal.payload["configuration_revision"]:
            raise ConflictError("Watchlist changed; draft a new proposal before confirmation.")
    if isinstance(inputs, PaperTradeInput):
        latest = _paper_preview(session, conversation, inputs)
        if latest["risk_state"] == RiskAction.BLOCK.value:
            raise TradingPolicyError("Blocked by risk engine; Agent confirmation cannot override.")
        if canonical_sha256(latest) != canonical_sha256(
            {key: proposal.payload.get(key) for key in latest}
        ):
            raise ConflictError("Trade proposal changed; draft a new Agent proposal.")
    return tool, inputs


def apply_journal_note(
    session: Session,
    proposal: StructuredActionProposal,
    conversation: Conversation,
    tool: Tool,
    inputs: JournalNoteInput,
) -> UUID | None:
    if inputs.journal_entry_id is None:
        return None
    row = require_journal(session, inputs.journal_entry_id, conversation, lock=True)
    tag = f"proposal:{proposal.proposal_id}"
    if tag in (row.tags or []):
        return row.id
    if journal_snapshot_hash(row) != proposal.payload.get("journal_snapshot_hash"):
        raise ConflictError("Journal entry changed; draft a new proposal before appending.")
    changes: dict[str, Any] = {"tags": [*(row.tags or []), "interactive_agent", tag]}
    if tool.name == "journal.record_mistake":
        changes["mistakes"] = [*(row.mistakes or []), inputs.text]
    else:
        label = tool.name.removeprefix("journal.").replace("_", " ")
        changes["lessons"] = "\n".join(
            part for part in (row.lessons, f"[{label}] {inputs.text}") if part
        )
    try:
        update = JournalEntryUpdate.model_validate(changes)
    except ValidationError as exc:
        raise ValidationAppError("Journal append exceeds the canonical field limits.") from exc
    return JournalService(session, AuditService(session)).update(row.id, update).id
