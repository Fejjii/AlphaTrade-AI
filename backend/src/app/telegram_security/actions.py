"""Telegram remote-action vocabulary and authorization-boundary rules.

``EXECUTE_PAPER_PLAN`` is intentionally absent. ``CLOSE`` is a known member but
unavailable. ``APPROVE`` may create an authorization intent only; it never executes.
"""

from __future__ import annotations

from enum import StrEnum

from app.telegram_security.errors import TelegramSecurityError, TelegramSecurityReason

PROTOCOL_VERSION = "telegram-security-protocol-v1"

# Inbound webhook adapter (future) must reject other Telegram update types.
ALLOWED_TELEGRAM_UPDATE_TYPES: frozenset[str] = frozenset({"message", "callback_query"})
MAX_INBOUND_UPDATE_BYTES = 64_000


class TelegramRemoteAction(StrEnum):
    """Allowed future Telegram action names.

    ``CLOSE`` remains in the enum so callers can distinguish "known but
    unavailable" from unknown names. It is not issuable or appliable.
    """

    STATUS = "STATUS"
    EXPLAIN = "EXPLAIN"
    SHOW_CHART = "SHOW_CHART"
    REJECT = "REJECT"
    SKIP = "SKIP"
    APPROVE = "APPROVE"
    REDUCE_RISK = "REDUCE_RISK"
    CLOSE = "CLOSE"


class ActionEffectKind(StrEnum):
    READ_ONLY_RESPONSE = "READ_ONLY_RESPONSE"
    REJECT_RESOURCE = "REJECT_RESOURCE"
    SKIP_RESOURCE = "SKIP_RESOURCE"
    AUTHORIZATION_INTENT = "AUTHORIZATION_INTENT"
    RISK_PREVIEW = "RISK_PREVIEW"
    NONE = "NONE"


AVAILABLE_TELEGRAM_ACTIONS: frozenset[TelegramRemoteAction] = frozenset(
    {
        TelegramRemoteAction.STATUS,
        TelegramRemoteAction.EXPLAIN,
        TelegramRemoteAction.SHOW_CHART,
        TelegramRemoteAction.REJECT,
        TelegramRemoteAction.SKIP,
        TelegramRemoteAction.APPROVE,
        TelegramRemoteAction.REDUCE_RISK,
    }
)

READ_ONLY_TELEGRAM_ACTIONS: frozenset[TelegramRemoteAction] = frozenset(
    {
        TelegramRemoteAction.STATUS,
        TelegramRemoteAction.EXPLAIN,
        TelegramRemoteAction.SHOW_CHART,
    }
)

CLOSE_AVAILABLE = False
APPROVE_EXECUTES = False
TELEGRAM_EXECUTION_ENTRY_PATHS: tuple[str, ...] = ()

_ACTION_EFFECTS: dict[TelegramRemoteAction, ActionEffectKind] = {
    TelegramRemoteAction.STATUS: ActionEffectKind.READ_ONLY_RESPONSE,
    TelegramRemoteAction.EXPLAIN: ActionEffectKind.READ_ONLY_RESPONSE,
    TelegramRemoteAction.SHOW_CHART: ActionEffectKind.READ_ONLY_RESPONSE,
    TelegramRemoteAction.REJECT: ActionEffectKind.REJECT_RESOURCE,
    TelegramRemoteAction.SKIP: ActionEffectKind.SKIP_RESOURCE,
    TelegramRemoteAction.APPROVE: ActionEffectKind.AUTHORIZATION_INTENT,
    TelegramRemoteAction.REDUCE_RISK: ActionEffectKind.RISK_PREVIEW,
}


def is_telegram_action_available(action: TelegramRemoteAction) -> bool:
    return action in AVAILABLE_TELEGRAM_ACTIONS and action is not TelegramRemoteAction.CLOSE


def effect_kind_for(action: TelegramRemoteAction) -> ActionEffectKind:
    if not is_telegram_action_available(action):
        return ActionEffectKind.NONE
    return _ACTION_EFFECTS[action]


def approve_creates_authorization_intent_only(action: TelegramRemoteAction) -> bool:
    return action is TelegramRemoteAction.APPROVE and not APPROVE_EXECUTES


def parse_remote_action(value: str) -> TelegramRemoteAction:
    """Parse a Telegram action name. ``CLOSE`` and unknown names fail closed."""
    normalized = value.strip().upper().replace(" ", "_").replace("-", "_")
    try:
        action = TelegramRemoteAction(normalized)
    except ValueError as exc:
        raise TelegramSecurityError(
            f"Unknown Telegram action {value!r}.",
            reason=TelegramSecurityReason.UNKNOWN_ACTION,
            details={"action": value},
        ) from exc
    if action is TelegramRemoteAction.CLOSE:
        raise TelegramSecurityError(
            "Telegram CLOSE is unavailable.",
            reason=TelegramSecurityReason.CLOSE_UNAVAILABLE,
        )
    if not is_telegram_action_available(action):
        raise TelegramSecurityError(
            f"Telegram action {action.value} is not allowed.",
            reason=TelegramSecurityReason.ACTION_NOT_ALLOWED,
            details={"action": action.value},
        )
    return action
