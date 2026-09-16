"""Deterministic helpers for Telegram security protocol tests."""

from __future__ import annotations

from uuid import UUID

from app.telegram_security.actions import TelegramRemoteAction
from app.telegram_security.clock import FrozenClock
from app.telegram_security.contracts import (
    ActionPayload,
    CallbackIdentity,
    ChatType,
    MessageIdentity,
    TelegramInboundUpdate,
)
from app.telegram_security.protocol import TelegramSecurityProtocol
from app.telegram_security.rate_limit import RateLimitPolicy
from app.telegram_security.transport import FakeTelegramTransport

ORG = UUID("00000000-0000-0000-0000-0000000000a1")
OTHER_ORG = UUID("00000000-0000-0000-0000-0000000000a2")
USER = UUID("00000000-0000-0000-0000-0000000000b1")
OTHER_USER = UUID("00000000-0000-0000-0000-0000000000b2")
ACCOUNT = UUID("00000000-0000-0000-0000-0000000000c1")
OTHER_ACCOUNT = UUID("00000000-0000-0000-0000-0000000000c2")
RESOURCE = UUID("00000000-0000-0000-0000-0000000000d1")
REVISION = UUID("00000000-0000-0000-0000-0000000000e1")
CONTENT_HASH = "a" * 64
BOT = "bot-100"
TG_USER = "tg-user-1"
OTHER_TG_USER = "tg-user-2"
CHAT = "tg-chat-1"
OTHER_CHAT = "tg-chat-2"
DEFAULT_INBOUND_BODY_SIZE = 1024


class TokenSeq:
    def __init__(self) -> None:
        self.n = 0

    def __call__(self) -> str:
        self.n += 1
        return f"token-{self.n:032d}"


def enabled_protocol(
    *,
    clock: FrozenClock | None = None,
    transport: FakeTelegramTransport | None = None,
    rate_limit_policy: RateLimitPolicy | None = None,
) -> TelegramSecurityProtocol:
    return TelegramSecurityProtocol.in_memory(
        enabled=True,
        clock=clock or FrozenClock(),
        transport=transport,
        token_factory=TokenSeq(),
        rate_limit_policy=rate_limit_policy,
    )


def message_identity(
    *,
    update_id: int = 1,
    telegram_user_id: str = TG_USER,
    chat_id: str = CHAT,
    chat_type: ChatType = ChatType.PRIVATE,
    bot_id: str = BOT,
    message_id: str = "msg-1",
) -> MessageIdentity:
    return MessageIdentity(
        bot_id=bot_id,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        chat_type=chat_type,
        update_id=update_id,
        message_id=message_id,
    )


def callback_identity(
    *,
    update_id: int = 10,
    callback_query_id: str = "cb-1",
    telegram_user_id: str = TG_USER,
    chat_id: str = CHAT,
    chat_type: ChatType = ChatType.PRIVATE,
    bot_id: str = BOT,
) -> CallbackIdentity:
    return CallbackIdentity(
        bot_id=bot_id,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        chat_type=chat_type,
        update_id=update_id,
        callback_query_id=callback_query_id,
    )


def payload(
    *,
    action: TelegramRemoteAction = TelegramRemoteAction.APPROVE,
    organization_id: UUID = ORG,
    user_id: UUID = USER,
    account_id: UUID = ACCOUNT,
    content_hash: str = CONTENT_HASH,
    revision_id: UUID | None = REVISION,
) -> ActionPayload:
    return ActionPayload(
        action=action,
        organization_id=organization_id,
        user_id=user_id,
        account_id=account_id,
        resource_type="trade_plan_revision",
        resource_id=RESOURCE,
        revision_id=revision_id,
        content_hash=content_hash,
    )


def inbound_message(*, body_size: int = DEFAULT_INBOUND_BODY_SIZE) -> TelegramInboundUpdate:
    """Authoritative message-update envelope. ``body_size`` is raw inbound bytes."""
    return TelegramInboundUpdate(update_type="message", body_size=body_size)


def inbound_callback(*, body_size: int = DEFAULT_INBOUND_BODY_SIZE) -> TelegramInboundUpdate:
    """Authoritative callback-update envelope. ``body_size`` is raw inbound bytes."""
    return TelegramInboundUpdate(update_type="callback_query", body_size=body_size)


def enroll(
    protocol: TelegramSecurityProtocol,
    *,
    organization_id: UUID = ORG,
    user_id: UUID = USER,
    identity: MessageIdentity | None = None,
) -> tuple[str, UUID]:
    started = protocol.start_enrollment(
        organization_id=organization_id, user_id=user_id, bot_id=BOT
    )
    completed = protocol.complete_enrollment(
        token=started.token,
        identity=identity or message_identity(),
        inbound=inbound_message(),
    )
    return started.token, completed.binding.binding_id
