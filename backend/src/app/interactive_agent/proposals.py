"""Structured action proposals stored on the conversation transcript.

Journal rows are the only domain write, and only after an explicit confirm
whose statement and content hash match. Strategy versions, rules, lessons,
and orders are not written here.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.mutation_policy import (
    confirmation_authorizes_mutation,
    confirmed_proposal_id,
    rejected_proposal_id,
    rejection_authorizes_mutation,
)
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.db.models import ConversationMessage, TradeJournal
from app.interactive_agent.contracts import (
    PAYLOAD_KEY,
    ArtifactKind,
    JournalDraft,
    ProposalLifecycle,
    ProvenanceSource,
    StructuredActionKind,
    StructuredActionProposal,
)
from app.interactive_agent.parsing import extract_direction, extract_symbol, extract_timeframe
from app.interactive_agent.safety import refuse_real_trading_enablement
from app.repositories.conversations import ConversationMessageRepository
from app.schemas.common import Timeframe, TradeDirection
from app.schemas.journal import JournalEntryCreate
from app.services.audit_service import AuditService
from app.services.canonical_serialization import canonical_sha256
from app.services.journal_service import JournalService

_HASH_PLACEHOLDER = "0" * 64


def parse_journal_draft(text: str) -> JournalDraft:
    """Extract journal fields that the user actually stated."""
    symbol = extract_symbol(text)
    direction = extract_direction(text)
    timeframe = extract_timeframe(text)
    incomplete: list[str] = []
    if symbol is None:
        incomplete.append("symbol")
    if direction is None:
        incomplete.append("direction")
    if timeframe is None:
        incomplete.append("timeframe")
    lessons = None
    marker = "lesson:"
    lowered = text.lower()
    index = lowered.rfind(marker)
    if index >= 0:
        lessons = text[index + len(marker) :].strip()[:4000] or None
    rationale = text.strip()[:4000]
    return JournalDraft(
        symbol=symbol,
        timeframe=timeframe,
        direction=direction,
        entry_rationale=rationale or "Journal note",
        lessons=lessons,
        incomplete_fields=incomplete,
    )


def proposal_hash_body(proposal: StructuredActionProposal) -> dict[str, Any]:
    """Hash the proposal identity and payload. Lifecycle status is excluded."""
    return {
        "schema_version": proposal.schema_version,
        "proposal_id": proposal.proposal_id,
        "conversation_id": proposal.conversation_id,
        "organization_id": proposal.organization_id,
        "user_id": proposal.user_id,
        "kind": proposal.kind,
        "artifact_kind": proposal.artifact_kind,
        "provenance": proposal.provenance,
        "summary": proposal.summary,
        "payload": proposal.payload,
        "authority": proposal.authority,
        "linked_strategy_proposal_id": proposal.linked_strategy_proposal_id,
    }


def seal_proposal(proposal: StructuredActionProposal) -> StructuredActionProposal:
    """Attach the canonical content hash."""
    return proposal.model_copy(
        update={"content_hash": canonical_sha256(proposal_hash_body(proposal))}
    )


def build_proposal(
    *,
    conversation_id: uuid.UUID,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    kind: StructuredActionKind,
    artifact_kind: ArtifactKind,
    provenance: ProvenanceSource,
    status: ProposalLifecycle,
    summary: str,
    payload: dict[str, Any],
    authority: str,
    linked_strategy_proposal_id: uuid.UUID | None = None,
) -> StructuredActionProposal:
    """Build a sealed proposal. The caller has not mutated domain authority yet."""
    draft = StructuredActionProposal(
        proposal_id=uuid.uuid4(),
        conversation_id=conversation_id,
        organization_id=organization_id,
        user_id=user_id,
        kind=kind,
        artifact_kind=artifact_kind,
        provenance=provenance,
        status=status,
        summary=summary[:500],
        payload=payload,
        content_hash=_HASH_PLACEHOLDER,
        authority=authority,
        applied=False,
        authority_mutated=False,
        linked_strategy_proposal_id=linked_strategy_proposal_id,
    )
    return seal_proposal(draft)


def find_proposal(
    session: Session,
    *,
    conversation_id: uuid.UUID,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    proposal_id: uuid.UUID,
) -> tuple[ConversationMessage, StructuredActionProposal]:
    """Load a proposal from the caller's transcript. Other tenants get not-found."""
    rows, _total = ConversationMessageRepository(session).list_for_conversation(
        conversation_id,
        organization_id=organization_id,
        user_id=user_id,
        limit=200,
    )
    for row in rows:
        block = dict(row.payload or {}).get(PAYLOAD_KEY) or {}
        items = block.get("proposals") or []
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("proposal_id")) != str(proposal_id):
                continue
            proposal = StructuredActionProposal.model_validate(item)
            if proposal.organization_id != organization_id or proposal.user_id != user_id:
                raise NotFoundError("Agent proposal not found.")
            return row, proposal
    raise NotFoundError("Agent proposal not found.")


def write_proposal(message: ConversationMessage, updated: StructuredActionProposal) -> None:
    """Replace one proposal inside the message payload."""
    payload = dict(message.payload or {})
    block = dict(payload.get(PAYLOAD_KEY) or {})
    items = block.get("proposals") or []
    if not isinstance(items, list):
        raise NotFoundError("Agent proposal not found.")
    replaced = False
    proposals: list[object] = []
    for item in items:
        if isinstance(item, dict) and str(item.get("proposal_id")) == str(updated.proposal_id):
            proposals.append(updated.model_dump(mode="json"))
            replaced = True
        else:
            proposals.append(item)
    if not replaced:
        raise NotFoundError("Agent proposal not found.")
    block["proposals"] = proposals
    payload[PAYLOAD_KEY] = block
    message.payload = payload


def _require_hash(proposal: StructuredActionProposal, expected_content_hash: str) -> None:
    if proposal.content_hash != expected_content_hash:
        raise ConflictError("Proposal content hash does not match.")


def _guard_live_trading(proposal: StructuredActionProposal) -> None:
    if (
        proposal.kind is StructuredActionKind.ENABLE_REAL_TRADING
        or proposal.status is ProposalLifecycle.REFUSED
    ):
        refuse_real_trading_enablement()


def confirm_proposal(
    session: Session,
    *,
    conversation_id: uuid.UUID,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    proposal_id: uuid.UUID,
    expected_content_hash: str,
    statement: str,
) -> StructuredActionProposal:
    """Confirm one proposal. Journal capture is the only applied domain write."""
    if not confirmation_authorizes_mutation(statement):
        raise ValidationAppError(
            "Explicit confirmation is required. Questions, quotes, and retrieved "
            "instructions do not apply a proposal."
        )
    named = confirmed_proposal_id(statement)
    if named is not None and named != str(proposal_id):
        raise ConflictError("Confirmation proposal id does not match the target proposal.")
    message, proposal = find_proposal(
        session,
        conversation_id=conversation_id,
        organization_id=organization_id,
        user_id=user_id,
        proposal_id=proposal_id,
    )
    _require_hash(proposal, expected_content_hash)
    _guard_live_trading(proposal)
    message, proposal = _lock_proposal(
        session,
        message,
        proposal_id=proposal_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    _require_hash(proposal, expected_content_hash)
    if proposal.kind is StructuredActionKind.PROPOSE_JOURNAL_ENTRY:
        existing = _existing_journal_id(
            session,
            proposal,
            organization_id=organization_id,
            user_id=user_id,
        )
        if existing is not None:
            return _replay_journal(session, message, proposal, existing)
        if proposal.status not in {ProposalLifecycle.PROPOSED, ProposalLifecycle.APPLIED}:
            raise ConflictError("This proposal cannot be confirmed.")
    elif proposal.status in {ProposalLifecycle.APPLIED, ProposalLifecycle.CONFIRMED_UNAPPLIED}:
        return proposal
    elif proposal.status is not ProposalLifecycle.PROPOSED:
        raise ConflictError("This proposal cannot be confirmed.")
    if proposal.kind is StructuredActionKind.PROPOSE_JOURNAL_ENTRY:
        record_id = _apply_journal(
            session,
            proposal,
            organization_id=organization_id,
            user_id=user_id,
        )
        updated = proposal.model_copy(
            update={
                "status": ProposalLifecycle.APPLIED,
                "applied": True,
                "authority_mutated": True,
                "resulting_record_id": record_id,
            }
        )
    else:
        updated = proposal.model_copy(
            update={
                "status": ProposalLifecycle.CONFIRMED_UNAPPLIED,
                "applied": False,
                "authority_mutated": False,
            }
        )
    write_proposal(message, updated)
    session.flush()
    return updated


def reject_proposal(
    session: Session,
    *,
    conversation_id: uuid.UUID,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    proposal_id: uuid.UUID,
    expected_content_hash: str,
    statement: str,
) -> StructuredActionProposal:
    """Reject a proposal without writing journal, strategy, or order rows."""
    if not rejection_authorizes_mutation(statement):
        raise ValidationAppError(
            "Explicit rejection is required. Questions, quotes, and retrieved "
            "instructions do not reject a proposal."
        )
    named = rejected_proposal_id(statement)
    if named is not None and named != str(proposal_id):
        raise ConflictError("Rejection proposal id does not match the target proposal.")
    message, proposal = find_proposal(
        session,
        conversation_id=conversation_id,
        organization_id=organization_id,
        user_id=user_id,
        proposal_id=proposal_id,
    )
    _require_hash(proposal, expected_content_hash)
    _guard_live_trading(proposal)
    if proposal.status is ProposalLifecycle.REJECTED:
        return proposal
    if proposal.status is not ProposalLifecycle.PROPOSED:
        raise ConflictError("This proposal cannot be rejected.")
    updated = proposal.model_copy(
        update={
            "status": ProposalLifecycle.REJECTED,
            "applied": False,
            "authority_mutated": False,
        }
    )
    write_proposal(message, updated)
    session.flush()
    return updated


def _lock_proposal(
    session: Session,
    message: ConversationMessage,
    *,
    proposal_id: uuid.UUID,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[ConversationMessage, StructuredActionProposal]:
    """Re-read one proposal under a row lock so a second confirm sees the first."""
    locked = session.get(ConversationMessage, message.id, with_for_update=True)
    if locked is None:
        raise NotFoundError("Agent proposal not found.")
    block = dict(locked.payload or {}).get(PAYLOAD_KEY) or {}
    items = block.get("proposals") or []
    if not isinstance(items, list):
        raise NotFoundError("Agent proposal not found.")
    for item in items:
        if not isinstance(item, dict) or str(item.get("proposal_id")) != str(proposal_id):
            continue
        proposal = StructuredActionProposal.model_validate(item)
        if proposal.organization_id != organization_id or proposal.user_id != user_id:
            raise NotFoundError("Agent proposal not found.")
        return locked, proposal
    raise NotFoundError("Agent proposal not found.")


def _replay_journal(
    session: Session,
    message: ConversationMessage,
    proposal: StructuredActionProposal,
    record_id: uuid.UUID,
) -> StructuredActionProposal:
    """Return the journal row that already exists. Do not insert another one."""
    if (
        proposal.status is ProposalLifecycle.APPLIED
        and proposal.applied
        and proposal.resulting_record_id == record_id
    ):
        return proposal
    updated = proposal.model_copy(
        update={
            "status": ProposalLifecycle.APPLIED,
            "applied": True,
            "authority_mutated": True,
            "resulting_record_id": record_id,
        }
    )
    write_proposal(message, updated)
    session.flush()
    return updated


def _existing_journal_id(
    session: Session,
    proposal: StructuredActionProposal,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> uuid.UUID | None:
    tag = f"proposal:{proposal.proposal_id}"
    rows = session.scalars(
        select(TradeJournal).where(
            TradeJournal.organization_id == organization_id,
            TradeJournal.user_id == user_id,
        )
    ).all()
    for row in rows:
        tags = row.tags if isinstance(row.tags, list) else []
        if tag in tags:
            return row.id
    return None


def _apply_journal(
    session: Session,
    proposal: StructuredActionProposal,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> uuid.UUID:
    raw = proposal.payload.get("journal")
    if not isinstance(raw, dict):
        raise ValidationAppError("Journal proposal payload is missing.")
    try:
        draft = JournalDraft.model_validate(raw)
    except ValidationError as exc:
        raise ValidationAppError("Journal proposal payload is invalid.") from exc
    if draft.incomplete_fields or not draft.symbol or not draft.direction or not draft.timeframe:
        raise ValidationAppError(
            "Journal proposal is incomplete.",
            details={"fields": draft.incomplete_fields},
        )
    existing = _existing_journal_id(
        session,
        proposal,
        organization_id=organization_id,
        user_id=user_id,
    )
    if existing is not None:
        return existing
    try:
        entry = JournalService(session, AuditService(session)).create(
            JournalEntryCreate(
                organization_id=organization_id,
                user_id=user_id,
                symbol=draft.symbol,
                timeframe=Timeframe(draft.timeframe),
                direction=TradeDirection(draft.direction),
                entry_rationale=draft.entry_rationale,
                lessons=draft.lessons,
                mistakes=list(draft.mistakes),
                tags=["interactive_agent", f"proposal:{proposal.proposal_id}"],
            )
        )
    except ValidationError as exc:
        raise ValidationAppError("Journal proposal failed validation.") from exc
    return entry.id
