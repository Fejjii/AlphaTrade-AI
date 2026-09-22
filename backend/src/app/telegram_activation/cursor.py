"""Durable polling offset. Replay stays idempotent if the offset is lost."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.telegram_activation.errors import TelegramActivationError


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
