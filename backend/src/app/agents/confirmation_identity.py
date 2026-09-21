"""User-visible confirmation identity for conversational strategy drafts.

Bare ``I confirm`` binds to the last presented proposal identity in the
conversation, not whichever draft is currently pending in the database.
"""

from __future__ import annotations

import re
from uuid import UUID

from pydantic import Field

from app.market_contracts.models import CanonicalModel
from app.schemas.agent import ConversationTurn
from app.schemas.conversation import StrategyProposalRecord

IDENTITY_BEGIN = "--- confirmation identity ---"
IDENTITY_END = "--- end confirmation identity ---"

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_BLOCK = re.compile(
    rf"{re.escape(IDENTITY_BEGIN)}\s*"
    rf"proposal_id:\s*({_UUID})\s*"
    r"content_hash:\s*([0-9a-f]{64})\s*"
    rf"target_strategy_id:\s*(none|{_UUID})\s*"
    rf"parent_version_id:\s*(none|{_UUID})\s*"
    rf"conversation_id:\s*({_UUID})\s*"
    rf"organization_id:\s*({_UUID})\s*"
    rf"user_id:\s*({_UUID})\s*"
    rf"{re.escape(IDENTITY_END)}",
    re.IGNORECASE,
)


class PresentedProposalIdentity(CanonicalModel):
    """Exact proposal identity presented to the user for confirmation."""

    conversation_id: UUID
    proposal_id: UUID
    content_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    target_strategy_id: UUID | None = None
    parent_version_id: UUID | None = None
    organization_id: UUID
    user_id: UUID


def identity_from_proposal(
    proposal: StrategyProposalRecord,
    *,
    conversation_id: UUID,
    organization_id: UUID,
    user_id: UUID,
) -> PresentedProposalIdentity:
    if not proposal.content_hash:
        raise ValueError("Proposal has no content hash to present for confirmation.")
    return PresentedProposalIdentity(
        conversation_id=conversation_id,
        proposal_id=proposal.id,
        content_hash=proposal.content_hash,
        target_strategy_id=proposal.target_strategy_id,
        parent_version_id=proposal.parent_version_id,
        organization_id=organization_id,
        user_id=user_id,
    )


def format_presented_confirmation_identity(identity: PresentedProposalIdentity) -> str:
    """Compact user-visible identity. Discussion text stays above this footer."""

    target = "none" if identity.target_strategy_id is None else str(identity.target_strategy_id)
    parent = "none" if identity.parent_version_id is None else str(identity.parent_version_id)
    return "\n".join(
        [
            IDENTITY_BEGIN,
            f"proposal_id: {identity.proposal_id}",
            f"content_hash: {identity.content_hash}",
            f"target_strategy_id: {target}",
            f"parent_version_id: {parent}",
            f"conversation_id: {identity.conversation_id}",
            f"organization_id: {identity.organization_id}",
            f"user_id: {identity.user_id}",
            IDENTITY_END,
            'Reply "I confirm" to accept this exact proposal. '
            "A newer draft requires a new explicit confirmation.",
        ]
    )


def parse_presented_confirmation_identity(content: str) -> PresentedProposalIdentity | None:
    matches = list(_BLOCK.finditer(content))
    if not matches:
        return None
    match = matches[-1]
    target_raw = match.group(3).lower()
    parent_raw = match.group(4).lower()
    return PresentedProposalIdentity(
        conversation_id=UUID(match.group(5)),
        proposal_id=UUID(match.group(1)),
        content_hash=match.group(2).lower(),
        target_strategy_id=None if target_raw == "none" else UUID(target_raw),
        parent_version_id=None if parent_raw == "none" else UUID(parent_raw),
        organization_id=UUID(match.group(6)),
        user_id=UUID(match.group(7)),
    )


def presented_confirmation_identity_from_history(
    turns: list[ConversationTurn],
) -> PresentedProposalIdentity | None:
    """Last assistant-presented identity. Server pending-draft lookup is not used."""

    last: PresentedProposalIdentity | None = None
    for turn in turns:
        if turn.role != "assistant":
            continue
        parsed = parse_presented_confirmation_identity(turn.content)
        if parsed is not None:
            last = parsed
    return last


def identity_matches_caller(
    identity: PresentedProposalIdentity,
    *,
    conversation_id: UUID,
    organization_id: UUID,
    user_id: UUID,
) -> bool:
    return (
        identity.conversation_id == conversation_id
        and identity.organization_id == organization_id
        and identity.user_id == user_id
    )


__all__ = [
    "IDENTITY_BEGIN",
    "IDENTITY_END",
    "PresentedProposalIdentity",
    "format_presented_confirmation_identity",
    "identity_from_proposal",
    "identity_matches_caller",
    "parse_presented_confirmation_identity",
    "presented_confirmation_identity_from_history",
]
