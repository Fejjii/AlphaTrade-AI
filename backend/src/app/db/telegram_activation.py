"""ORM models for paper Telegram activation cursor and send ledger.

These tables do not authorize trading. Delivery state remains on the security outbox.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TelegramActivationCursorRow(Base):
    __tablename__ = "telegram_activation_inbound_cursors"

    bot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    last_update_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TelegramActivationSendLedgerRow(Base):
    __tablename__ = "telegram_activation_send_ledger"
    __table_args__ = (
        UniqueConstraint(
            "bot_id",
            "idempotency_key",
            name="uq_tg_activation_send_bot_key",
        ),
    )

    ledger_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    bot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    transport_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
