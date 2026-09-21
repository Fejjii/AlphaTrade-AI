"""Identity-bound confirmation footer for paper Telegram mutations."""

from __future__ import annotations

import re
from uuid import UUID

from app.telegram_paper_agent.contracts import PresentedPaperConfirmation
from app.telegram_security.actions import TelegramRemoteAction
from app.telegram_security.contracts import ActionPayload
from app.telegram_security.hashing import payload_binding_hash

IDENTITY_BEGIN = "--- paper confirmation identity ---"
IDENTITY_END = "--- end paper confirmation identity ---"
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_BLOCK = re.compile(
    rf"{re.escape(IDENTITY_BEGIN)}\s*"
    rf"action:\s*([A-Z_]+)\s*"
    rf"resource_type:\s*([a-z_]+)\s*"
    rf"resource_id:\s*({_UUID})\s*"
    r"content_hash:\s*([0-9a-f]{64})\s*"
    rf"revision_id:\s*(none|{_UUID})\s*"
    rf"organization_id:\s*({_UUID})\s*"
    rf"user_id:\s*({_UUID})\s*"
    rf"account_id:\s*({_UUID})\s*"
    rf"{re.escape(IDENTITY_END)}",
    re.IGNORECASE,
)


def format_paper_confirmation(row: PresentedPaperConfirmation) -> str:
    revision = "none" if row.revision_id is None else str(row.revision_id)
    return "\n".join(
        [
            IDENTITY_BEGIN,
            f"action: {row.action.value}",
            f"resource_type: {row.resource_type}",
            f"resource_id: {row.resource_id}",
            f"content_hash: {row.content_hash}",
            f"revision_id: {revision}",
            f"organization_id: {row.organization_id}",
            f"user_id: {row.user_id}",
            f"account_id: {row.account_id}",
            IDENTITY_END,
            f'Reply "I confirm {row.action.value.lower()}" with this exact identity. '
            "This is not execution authority and cannot place a live order.",
        ]
    )


def parse_paper_confirmation_payload(content: str) -> ActionPayload | None:
    matches = list(_BLOCK.finditer(content))
    if not matches:
        return None
    match = matches[-1]
    revision_raw = match.group(5).lower()
    try:
        action = TelegramRemoteAction(match.group(1).upper())
    except ValueError:
        return None
    return ActionPayload(
        action=action,
        organization_id=UUID(match.group(6)),
        user_id=UUID(match.group(7)),
        account_id=UUID(match.group(8)),
        resource_type=match.group(2).lower(),
        resource_id=UUID(match.group(3)),
        revision_id=None if revision_raw == "none" else UUID(revision_raw),
        content_hash=match.group(4).lower(),
    )


def payload_from_presented(row: PresentedPaperConfirmation) -> ActionPayload:
    payload = ActionPayload(
        action=row.action,
        organization_id=row.organization_id,
        user_id=row.user_id,
        account_id=row.account_id,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        revision_id=row.revision_id,
        content_hash=row.content_hash,
    )
    if payload_binding_hash(payload) != row.payload_hash:
        raise ValueError("Presented confirmation payload hash does not match.")
    return payload
