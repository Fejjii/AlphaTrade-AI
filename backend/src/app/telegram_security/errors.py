"""Fail-closed errors for the isolated Telegram security protocol."""

from __future__ import annotations

from enum import StrEnum


class TelegramSecurityReason(StrEnum):
    FEATURE_DISABLED = "FEATURE_DISABLED"
    UPDATE_TYPE_REJECTED = "UPDATE_TYPE_REJECTED"
    UPDATE_TOO_LARGE = "UPDATE_TOO_LARGE"
    CHAT_NOT_PRIVATE = "CHAT_NOT_PRIVATE"
    ENROLLMENT_NOT_FOUND = "ENROLLMENT_NOT_FOUND"
    ENROLLMENT_EXPIRED = "ENROLLMENT_EXPIRED"
    ENROLLMENT_USED = "ENROLLMENT_USED"
    ENROLLMENT_WRONG_BOT = "ENROLLMENT_WRONG_BOT"
    ENROLLMENT_CHAT_ID_ONLY = "ENROLLMENT_CHAT_ID_ONLY"
    BINDING_NOT_FOUND = "BINDING_NOT_FOUND"
    BINDING_REVOKED = "BINDING_REVOKED"
    TELEGRAM_USER_ALREADY_BOUND = "TELEGRAM_USER_ALREADY_BOUND"
    NONCE_NOT_FOUND = "NONCE_NOT_FOUND"
    NONCE_EXPIRED = "NONCE_EXPIRED"
    NONCE_USED = "NONCE_USED"
    PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"
    CROSS_USER = "CROSS_USER"
    CROSS_ORGANIZATION = "CROSS_ORGANIZATION"
    CROSS_ACCOUNT = "CROSS_ACCOUNT"
    CROSS_CHAT = "CROSS_CHAT"
    CROSS_BOT = "CROSS_BOT"
    CLOSE_UNAVAILABLE = "CLOSE_UNAVAILABLE"
    UNKNOWN_ACTION = "UNKNOWN_ACTION"
    ACTION_NOT_ALLOWED = "ACTION_NOT_ALLOWED"
    RATE_LIMITED = "RATE_LIMITED"
    TRANSPORT_FAILURE = "TRANSPORT_FAILURE"
    OUTBOX_CONFLICT = "OUTBOX_CONFLICT"
    OUTBOX_NOT_FOUND = "OUTBOX_NOT_FOUND"
    ACK_STATE_INVALID = "ACK_STATE_INVALID"


class TelegramSecurityError(Exception):
    """Protocol-level failure. ``reason`` is the stable machine code."""

    def __init__(
        self,
        message: str,
        *,
        reason: TelegramSecurityReason,
        details: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason
        self.details = details or {}


class TelegramInteractionDisabledError(TelegramSecurityError):
    def __init__(self) -> None:
        super().__init__(
            "Telegram interaction protocol is disabled.",
            reason=TelegramSecurityReason.FEATURE_DISABLED,
        )


class TelegramRateLimitedError(TelegramSecurityError):
    def __init__(self, *, scope: str) -> None:
        super().__init__(
            "Telegram protocol rate limit exceeded.",
            reason=TelegramSecurityReason.RATE_LIMITED,
            details={"scope": scope},
        )
