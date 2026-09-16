"""Isolated Telegram security and interaction protocol.

This package is not wired to FastAPI, execution, BloFin, or PostgreSQL.
Telegram interaction remains disabled unless a caller constructs the protocol
with ``enabled=True``. ``APPROVE`` never executes. ``CLOSE`` is unavailable.
"""

from app.telegram_security.actions import (
    ALLOWED_TELEGRAM_UPDATE_TYPES,
    APPROVE_EXECUTES,
    AVAILABLE_TELEGRAM_ACTIONS,
    CLOSE_AVAILABLE,
    MAX_INBOUND_UPDATE_BYTES,
    PROTOCOL_VERSION,
    TELEGRAM_EXECUTION_ENTRY_PATHS,
    ActionEffectKind,
    TelegramRemoteAction,
    parse_remote_action,
)
from app.telegram_security.clock import Clock, FrozenClock
from app.telegram_security.contracts import (
    ActionNonce,
    ActionOutcome,
    ActionPayload,
    ActionReceipt,
    ActionReceiptState,
    AuthorizationIntent,
    CallbackIdentity,
    ChatType,
    EnrollmentChallengeState,
    InboundReplayFingerprint,
    MessageIdentity,
    NonceState,
    OutboxState,
    TelegramBinding,
    TelegramInboundUpdate,
)
from app.telegram_security.errors import (
    TelegramInteractionDisabledError,
    TelegramRateLimitedError,
    TelegramSecurityError,
    TelegramSecurityReason,
)
from app.telegram_security.memory import InMemoryTelegramSecurityStore
from app.telegram_security.protocol import TelegramSecurityProtocol
from app.telegram_security.rate_limit import RateLimitPolicy
from app.telegram_security.transport import FakeTelegramBehavior, FakeTelegramTransport

__all__ = [
    "ALLOWED_TELEGRAM_UPDATE_TYPES",
    "APPROVE_EXECUTES",
    "AVAILABLE_TELEGRAM_ACTIONS",
    "CLOSE_AVAILABLE",
    "MAX_INBOUND_UPDATE_BYTES",
    "PROTOCOL_VERSION",
    "TELEGRAM_EXECUTION_ENTRY_PATHS",
    "ActionEffectKind",
    "ActionNonce",
    "ActionOutcome",
    "ActionPayload",
    "ActionReceipt",
    "ActionReceiptState",
    "AuthorizationIntent",
    "CallbackIdentity",
    "ChatType",
    "Clock",
    "EnrollmentChallengeState",
    "FakeTelegramBehavior",
    "FakeTelegramTransport",
    "FrozenClock",
    "InMemoryTelegramSecurityStore",
    "InboundReplayFingerprint",
    "MessageIdentity",
    "NonceState",
    "OutboxState",
    "RateLimitPolicy",
    "TelegramBinding",
    "TelegramInboundUpdate",
    "TelegramInteractionDisabledError",
    "TelegramRateLimitedError",
    "TelegramRemoteAction",
    "TelegramSecurityError",
    "TelegramSecurityProtocol",
    "TelegramSecurityReason",
    "parse_remote_action",
]
