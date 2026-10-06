"""Scoped transcript references and bounded conversational context, never authority."""

import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Conversation, ConversationMessage, ExecutionAccount, JournalTrade
from app.interactive_agent.actions import ActionRequest, RecordedTradeInput
from app.interactive_agent.contracts import (
    PAYLOAD_KEY,
    AgentTurnRequest,
    ArtifactKind,
    ConnectionRef,
)
from app.interactive_agent.parsing import extract_direction, extract_symbol
from app.interactive_agent.recorded_trade import is_current_setup_request
from app.providers.llm import LLMMessage
from app.schemas.common import ConversationMessageRole, StrictModel
from app.services.conversation_service import ConversationService

FACTS_MARKER = "\n\nRecorded facts (not a confirmation):\n"
_VERSION = "ConversationTrade/v1"
_NO_SELECTION = (
    "Which trade do you mean? Ask for a specific market and direction, "
    "such as your latest BTC short paper trade. "
    "This conversation has no unambiguous selected trade."
)
_MUTATION = re.compile(
    r"\b(?:prepare|execute|submit|activate|approve|place|create|log|save)\b", re.I
)
_FOLLOWUP = re.compile(
    r"\b(?:that|this|same)\s+(?:(?:paper|same|recorded|approved)\s+)?(?:trade|plan)\b|"
    r"\b(?:explain|describe|summari[sz]e)\s+it\b|"
    r"\b(?:why|how|where|what)\b.{0,70}\b(?:it|its)\b|"
    r"\bwhat\s+(?:was|were)\s+(?:the|its)\s+"
    r"(?:entry|fills?|stop|targets?|authorization|venue|fees?|outcome)\b",
    re.I,
)


class TradeReference(StrictModel):
    journal_trade_id: UUID
    account_id: UUID | None
    organization_id: UUID
    user_id: UUID
    symbol: str = Field(min_length=1, max_length=30)


class StoredTradeContext(StrictModel):
    schema_version: Literal["ConversationTrade/v1"] = "ConversationTrade/v1"
    conversation_id: UUID
    organization_id: UUID
    user_id: UUID
    selected: TradeReference | None


@dataclass(frozen=True)
class FollowupResolution:
    action: ActionRequest | None
    missing_context: str | None = None


def _symbol(value: str) -> str:
    return value.upper().replace("-", "").replace("/", "")


def _stored_reference(session: Session, conversation: Conversation) -> TradeReference | None:
    rows = list(
        session.scalars(
            select(ConversationMessage)
            .where(
                ConversationMessage.conversation_id == conversation.id,
                ConversationMessage.organization_id == conversation.organization_id,
                ConversationMessage.user_id == conversation.user_id,
                ConversationMessage.role == ConversationMessageRole.ASSISTANT,
                ConversationMessage.payload[PAYLOAD_KEY]["trade_context"][
                    "schema_version"
                ].as_string()
                == _VERSION,
            )
            .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
            .limit(2)
        )
    )
    if not rows:
        return None
    # Equal clocks with different references do not establish a latest selection.
    if (
        len(rows) == 2
        and rows[0].created_at == rows[1].created_at
        and rows[0].payload[PAYLOAD_KEY]["trade_context"]
        != rows[1].payload[PAYLOAD_KEY]["trade_context"]
    ):
        return None
    try:
        context = StoredTradeContext.model_validate(rows[0].payload[PAYLOAD_KEY]["trade_context"])
    except (ValidationError, KeyError, TypeError):
        return None
    if (
        context.conversation_id,
        context.organization_id,
        context.user_id,
    ) != (conversation.id, conversation.organization_id, conversation.user_id):
        return None
    reference = context.selected
    if reference is None:
        return None  # A failed explicit selection invalidates the previous one.
    if (reference.organization_id, reference.user_id) != (
        conversation.organization_id,
        conversation.user_id,
    ):
        return None
    found = session.scalar(
        select(JournalTrade.id).where(
            JournalTrade.id == reference.journal_trade_id,
            JournalTrade.organization_id == reference.organization_id,
            JournalTrade.user_id == reference.user_id,
            JournalTrade.account_id == reference.account_id,
        )
    )
    return reference if found is not None else None


def resolve_trade_followup(
    session: Session,
    *,
    conversation: Conversation,
    request: AgentTurnRequest,
    routed: ActionRequest | None,
) -> FollowupResolution:
    if request.action is not None or request.analytics_filters is not None:
        return FollowupResolution(routed)
    if is_current_setup_request(request.message):
        return FollowupResolution(routed)
    if _MUTATION.search(request.message) or not _FOLLOWUP.search(request.message):
        return FollowupResolution(routed)
    if routed is not None and routed.name != "paper_trade.read_recorded":
        return FollowupResolution(routed)
    selectors = (
        RecordedTradeInput.model_validate(routed.arguments) if routed else RecordedTradeInput()
    )
    explicit_symbol = extract_symbol(request.message)
    if (
        selectors.journal_trade_id is not None
        or selectors.account_id is not None
        or selectors.direction is not None
        or selectors.latest
        or selectors.market_name is not None
        or explicit_symbol is not None
    ):
        return FollowupResolution(
            routed
            or ActionRequest(
                name="paper_trade.read_recorded",
                arguments={
                    "symbol": explicit_symbol,
                    "direction": extract_direction(request.message),
                },
            )
        )
    reference = _stored_reference(session, conversation)
    if (
        reference is not None
        and request.symbol
        and _symbol(request.symbol) != _symbol(reference.symbol)
    ):
        # A changed UI market is an explicit new selection, not the old trade.
        return FollowupResolution(
            ActionRequest(name="paper_trade.read_recorded", arguments={"symbol": request.symbol})
        )
    if reference is None:
        return FollowupResolution(
            ActionRequest(name="paper_trade.read_recorded", arguments={}), _NO_SELECTION
        )
    return FollowupResolution(
        ActionRequest(
            name="paper_trade.read_recorded",
            arguments={
                "journal_trade_id": str(reference.journal_trade_id),
                "account_id": str(reference.account_id) if reference.account_id else None,
                "paper_only": selectors.paper_only,
            },
        )
    )


def conversational_history(
    service: ConversationService, conversation: Conversation
) -> tuple[LLMMessage, ...]:
    """Last four exchanges, at most 8,000 characters; exclude old raw evidence."""
    budget = 8000
    messages: list[LLMMessage] = []
    for turn in reversed(service.history_turns(conversation, limit=8)):
        text = turn.content.split(FACTS_MARKER, 1)[0] if turn.role == "assistant" else turn.content
        limit = min(1600, budget)
        if limit <= 0:
            break
        if len(text) > limit:
            text = text[: max(0, limit - 2)].rsplit(" ", 1)[0] + " …"
        text = text.strip()
        if text:
            messages.append(
                LLMMessage(role="assistant" if turn.role == "assistant" else "user", content=text)
            )
            budget -= len(text)
    return tuple(reversed(messages))


def context_from_sources(
    session: Session, conversation: Conversation, sources: list[ConnectionRef]
) -> StoredTradeContext:
    """Persist only a single scoped Journal identity produced by a server read."""
    identities: set[UUID] = set()
    for source in sources:
        if source.artifact_kind == ArtifactKind.JOURNAL_ENTRY:
            try:
                identities.add(UUID(source.record_id))
            except ValueError:
                continue
    trade = None
    if len(identities) == 1:
        trade = session.scalar(
            select(JournalTrade).where(
                JournalTrade.id.in_(identities),
                JournalTrade.organization_id == conversation.organization_id,
                JournalTrade.user_id == conversation.user_id,
                (
                    JournalTrade.account_id.is_(None)
                    | select(ExecutionAccount.id)
                    .where(
                        ExecutionAccount.id == JournalTrade.account_id,
                        ExecutionAccount.organization_id == conversation.organization_id,
                        ExecutionAccount.user_id == conversation.user_id,
                    )
                    .exists()
                ),
            )
        )
    reference = (
        TradeReference(
            journal_trade_id=trade.id,
            account_id=trade.account_id,
            organization_id=trade.organization_id,
            user_id=trade.user_id,
            symbol=trade.symbol,
        )
        if trade is not None
        else None
    )
    return StoredTradeContext(
        conversation_id=conversation.id,
        organization_id=conversation.organization_id,
        user_id=conversation.user_id,
        selected=reference,
    )
