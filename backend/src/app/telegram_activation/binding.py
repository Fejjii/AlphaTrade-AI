"""Recipient binding checks. Bindings are never created from a chat id alone."""

from __future__ import annotations

from app.telegram_paper_agent.contracts import PaperAlertRecipient
from app.telegram_security.actions import TelegramRemoteAction
from app.telegram_security.contracts import BindingState, ChatType, TelegramBinding
from app.telegram_security.persistence import TelegramSecurityStore

_TENANT_BLOCKERS = frozenset(
    {
        "recipient_tenant_mismatch",
        "recipient_user_mismatch",
        "recipient_bot_mismatch",
        "recipient_chat_mismatch",
        "telegram_user_cross_tenant",
        "telegram_user_binding_conflict",
    }
)


def binding_blockers(
    binding: TelegramBinding | None,
    recipient: PaperAlertRecipient,
) -> tuple[str, ...]:
    """Return stable blocker codes. The codes do not contain identifiers."""
    if binding is None:
        return ("recipient_binding_missing",)
    blockers: list[str] = []
    if binding.state is not BindingState.VERIFIED or binding.revoked_at is not None:
        blockers.append("recipient_binding_not_verified")
    if binding.chat_type is not ChatType.PRIVATE:
        blockers.append("recipient_chat_not_private")
    if binding.organization_id != recipient.organization_id:
        blockers.append("recipient_tenant_mismatch")
    if binding.user_id != recipient.user_id:
        blockers.append("recipient_user_mismatch")
    if binding.bot_id != recipient.bot_id:
        blockers.append("recipient_bot_mismatch")
    if binding.chat_id != recipient.chat_id:
        blockers.append("recipient_chat_mismatch")
    if TelegramRemoteAction.CLOSE in binding.allowed_actions:
        blockers.append("binding_allows_close")
    return tuple(blockers)


def assess_recipient(
    store: TelegramSecurityStore,
    recipient: PaperAlertRecipient,
) -> tuple[str, ...]:
    """Binding plus one-bot-one-tenant checks against the security store."""
    binding = store.get_binding(recipient.binding_id)
    blockers = list(binding_blockers(binding, recipient))
    if binding is None:
        return tuple(blockers)
    active = store.get_active_binding_for_telegram_user(
        bot_id=binding.bot_id,
        telegram_user_id=binding.telegram_user_id,
    )
    if active is not None and active.binding_id != binding.binding_id:
        blockers.append("telegram_user_binding_conflict")
    if active is not None and active.organization_id != recipient.organization_id:
        blockers.append("telegram_user_cross_tenant")
    return tuple(blockers)


def recipient_is_bound(blockers: tuple[str, ...]) -> bool:
    return not any(
        code in blockers for code in ("recipient_binding_missing", "recipient_binding_not_verified")
    )


def recipient_is_private(blockers: tuple[str, ...], bound: bool) -> bool:
    return bound and "recipient_chat_not_private" not in blockers


def recipient_is_isolated(blockers: tuple[str, ...], bound: bool) -> bool:
    return bound and not any(code in _TENANT_BLOCKERS for code in blockers)
