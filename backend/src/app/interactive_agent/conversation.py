"""Conversational reply for an agent turn.

The existing model router writes the prose. That prose is not confirmation
and cannot change a proposal, journal row, or strategy version.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Protocol

import structlog
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.providers.factory import resolve_providers
from app.providers.llm import LLMMessage
from app.schemas.model_routing import (
    ModelCallerScope,
    ModelContextScope,
    ModelResourceType,
    ModelRoutingPurpose,
    ModelTaskRequest,
)
from app.services.model_call_telemetry import ModelCallTelemetryService
from app.services.model_router import ModelRouter

logger = structlog.get_logger(__name__)

MODEL_REPLY_UNAVAILABLE = "Conversational model reply is unavailable."
_FACTS_HEADER = "Recorded facts (not a confirmation):"
_REPLY_LIMIT = 4000
_PROSE_LIMIT = 2000

_SYSTEM = (
    "You are AlphaTrade's paper-only conversational assistant. "
    "Reply in plain text to the user message. "
    "Be concise: give the conclusion, material blockers, and one next action. "
    "You cannot confirm, save, reject, or execute anything. "
    "Do not say a journal entry, strategy, rule, lesson, or order was saved or confirmed. "
    "Strategy rules, approval status, setup state and evidence availability must come from "
    "the supplied stored facts. If a detail is absent, say it is unavailable; distinguish "
    "general strategy explanations from the user's actual approved rules. "
    "Research validation, selected-version lifecycle approval, setup confirmation and "
    "execution eligibility are separate states. Approval comes only from the selected "
    "version's latest canonical lifecycle event, never a research-validation label. "
    "If the facts say canonical perpetual evidence is unavailable or stale, "
    "repeat unavailable or stale. Do not invent a price. "
    "Structured proposals are separate from this reply and stay unconfirmed until "
    "an explicit confirm request."
)


class ConversationalResponder(Protocol):
    """Produces assistant prose. It must not mutate domain records."""

    def compose(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message: str,
        factual_context: str,
    ) -> str: ...


class ModelConversationalResponder:
    """Route one general-agent completion through the existing model router."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def compose(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message: str,
        factual_context: str,
    ) -> str:
        try:
            providers = resolve_providers(self._settings)
            router = ModelRouter.from_settings(
                providers.llm,
                self._settings,
                # Keep telemetry off this session. An isolated usage transaction
                # on the request connection can roll back the transcript.
                telemetry=ModelCallTelemetryService(None),
            )
            result = router.complete(
                ModelTaskRequest(
                    purpose=ModelRoutingPurpose.GENERAL_AGENT_SYNTHESIS,
                    context=ModelContextScope(
                        organization_id=organization_id,
                        user_id=user_id,
                        resource_type=ModelResourceType.CONVERSATION,
                        resource_id=conversation_id,
                        purpose=ModelRoutingPurpose.GENERAL_AGENT_SYNTHESIS,
                    ),
                    correlation_id=str(uuid.uuid4()),
                    caller_organization_id=organization_id,
                    caller_user_id=user_id,
                    caller_scope=ModelCallerScope.USER,
                    caller_resource_type=ModelResourceType.CONVERSATION,
                    caller_resource_id=conversation_id,
                    temperature=0.0,
                ),
                [
                    LLMMessage(role="system", content=_SYSTEM),
                    LLMMessage(
                        role="user",
                        content=(
                            f"User message:\n{message.strip()}\n\n"
                            "Stored facts. Repeat unavailable or stale exactly. "
                            "Do not invent prices. Do not claim a record was confirmed.\n"
                            f"{factual_context[:16000]}"
                        ),
                    ),
                ],
            )
        except Exception:
            logger.warning("interactive_agent_model_reply_unavailable")
            return MODEL_REPLY_UNAVAILABLE
        logger.info(
            "interactive_agent_model_call",
            conversation_id=str(conversation_id),
            requested_model=result.decision.selected_model,
            resolved_model=result.resolved_model,
            fallback_used=result.fallback_used,
            unavailable=result.unavailable,
        )
        if result.unavailable or result.mutation_allowed:
            return MODEL_REPLY_UNAVAILABLE
        text = _prose(result.content)
        if not text:
            return MODEL_REPLY_UNAVAILABLE
        return text


def compose_visible_reply(model_text: str, factual: str) -> str:
    """Reserve prose space; the full evidence is stored separately in the transcript payload."""
    prose = model_text.strip() or MODEL_REPLY_UNAVAILABLE
    warnings = []
    if re.search(r"(?:is|freshness|quality|=)\s*stale\b", factual, re.I):
        warnings.append("Stored evidence is stale; it cannot establish a current price.")
    if re.search(
        r"(?:is|freshness|quality|=)\s*(?:unavailable|missing|incomplete)\b", factual, re.I
    ):
        warnings.append("Stored evidence is unavailable or incomplete; do not infer missing facts.")
    if "Current market conditions are unknown." in factual:
        warnings.append("Current market conditions are unknown.")
    lead = prose[:_PROSE_LIMIT]
    if warnings:
        lead += "\n\n" + " ".join(warnings)
    header = f"\n\n{_FACTS_HEADER}\n"
    budget = _REPLY_LIMIT - len(lead) - len(header)
    facts = factual.strip()
    if len(facts) > budget:
        note = "\nEvidence excerpt; full stored evidence is available in details."
        facts = facts[: budget - len(note)] + note
    return lead + header + facts


def _prose(content: str) -> str:
    text = content.strip()
    if not text:
        return ""
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return text[:2000]
        if isinstance(payload, dict):
            summary = payload.get("summary")
            if isinstance(summary, str) and summary.strip():
                return summary.strip()[:2000]
    return text[:2000]
