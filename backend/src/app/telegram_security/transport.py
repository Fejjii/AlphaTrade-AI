"""Telegram transport abstraction and a deterministic fake (no network I/O)."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class TransportSendResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    retryable: bool = False
    transport_message_id: str | None = None
    error_code: str | None = None


class TelegramTransport(Protocol):
    """Outbound private-chat transport. Implementations must not place orders."""

    def send_private_message(
        self,
        *,
        bot_id: str,
        chat_id: str,
        text: str,
        idempotency_key: str,
    ) -> TransportSendResult:
        """Send one private-chat message. Same idempotency key must converge."""


class FakeTelegramBehavior(StrEnum):
    ACCEPT = "ACCEPT"
    FAIL = "FAIL"


class FakeSentMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bot_id: str
    chat_id: str
    text: str
    idempotency_key: str
    transport_message_id: str


class FakeTelegramTransport:
    """In-process Telegram fake. Duplicate idempotency keys return the original message id."""

    def __init__(self, *, behavior: FakeTelegramBehavior = FakeTelegramBehavior.ACCEPT) -> None:
        self.behavior = behavior
        self.fail_times_remaining = 0
        self.attempts: list[str] = []
        self.sent: list[FakeSentMessage] = []
        self._message_ids: dict[str, str] = {}
        self._seq = 0

    def fail_next(self, times: int = 1) -> None:
        self.fail_times_remaining = times

    def send_private_message(
        self,
        *,
        bot_id: str,
        chat_id: str,
        text: str,
        idempotency_key: str,
    ) -> TransportSendResult:
        self.attempts.append(idempotency_key)
        if self.fail_times_remaining > 0:
            self.fail_times_remaining -= 1
            return TransportSendResult(
                ok=False,
                retryable=True,
                error_code="TRANSPORT_FAILURE",
            )
        if self.behavior is FakeTelegramBehavior.FAIL:
            return TransportSendResult(
                ok=False,
                retryable=True,
                error_code="TRANSPORT_FAILURE",
            )
        existing = self._message_ids.get(idempotency_key)
        if existing is not None:
            return TransportSendResult(ok=True, transport_message_id=existing)
        self._seq += 1
        message_id = f"tg-msg-{self._seq}"
        self._message_ids[idempotency_key] = message_id
        self.sent.append(
            FakeSentMessage(
                bot_id=bot_id,
                chat_id=chat_id,
                text=text,
                idempotency_key=idempotency_key,
                transport_message_id=message_id,
            )
        )
        return TransportSendResult(ok=True, transport_message_id=message_id)

    @property
    def send_count(self) -> int:
        return len(self.sent)
