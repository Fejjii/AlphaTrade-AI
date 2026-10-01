"""Exact paper action grammar. Narrative/model output cannot confirm an action."""

from __future__ import annotations

import re
import shlex
from uuid import UUID

from app.schemas.agent_paper import AgentPaperConfirmation, AgentPaperTradeIntent

PREPARE_PREFIX = "prepare paper trade"
CONFIRM_PREFIX = "confirm paper execution"
_CONFIRM = re.compile(
    r"Confirm paper execution revision=([0-9a-fA-F-]{36}) hash=([0-9a-f]{64})", re.I
)


def parse_paper_intent(message: str) -> AgentPaperTradeIntent:
    if not message.strip().lower().startswith(PREPARE_PREFIX):
        raise ValueError("Use Prepare paper trade followed by the structured trade details.")
    payload = message.strip()[len(PREPARE_PREFIX) :].strip()
    if payload.startswith("{"):
        return AgentPaperTradeIntent.model_validate_json(payload)
    fields: dict[str, object] = {}
    for token in shlex.split(payload):
        key, separator, value = token.partition("=")
        if not separator or key in fields or not value:
            raise ValueError("Trade details require unique, explicit field=value tokens.")
        fields[key] = value.split(",") if key == "targets" else value
    return AgentPaperTradeIntent.model_validate(fields)


def parse_paper_confirmation(message: str) -> AgentPaperConfirmation:
    matched = _CONFIRM.fullmatch(message.strip())
    if matched is None:
        raise ValueError("Confirmation must contain only the exact presented revision and hash.")
    return AgentPaperConfirmation(revision_id=UUID(matched[1]), plan_content_hash=matched[2])
