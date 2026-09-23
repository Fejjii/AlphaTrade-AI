"""Durable polling offset. Replay stays idempotent if the offset is lost."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict

from app.telegram_activation.errors import TelegramActivationError

_ENROLLMENT_CURSOR_NAMESPACE = UUID("6f0c1a2b-3c4d-5e6f-7081-92a3b4c5d6e7")


def enrollment_cursor_owner(bot_id: str) -> UUID:
    """Stable offset owner used before a verified binding exists.

    This is transport state for one bot. It is not a tenant authority.
    """

    return uuid5(_ENROLLMENT_CURSOR_NAMESPACE, f"telegram-enrollment-cursor:{bot_id}")


class InboundCursor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bot_id: str
    organization_id: UUID
    last_update_id: int
    updated_at: datetime


class ActivationCursorStore(Protocol):
    def get_cursor(self, *, bot_id: str) -> InboundCursor | None: ...

    def save_cursor(self, row: InboundCursor) -> None: ...


class InMemoryActivationCursorStore:
    """Process-local cursor. Tests and the refusing default use this."""

    def __init__(self) -> None:
        self._rows: dict[str, InboundCursor] = {}

    def get_cursor(self, *, bot_id: str) -> InboundCursor | None:
        return self._rows.get(bot_id)

    def save_cursor(self, row: InboundCursor) -> None:
        current = self._rows.get(row.bot_id)
        if current is not None and current.organization_id != row.organization_id:
            raise TelegramActivationError(
                "Inbound cursor is bound to another organization.",
                reason="tenant_conflict",
            )
        if current is not None and row.last_update_id < current.last_update_id:
            raise TelegramActivationError(
                "Inbound cursor cannot move backwards.",
                reason="cursor_regression",
            )
        self._rows[row.bot_id] = row
