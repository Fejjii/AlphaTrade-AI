"""paper Telegram activation cursor and send ledger

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-09-22 14:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e0f1a2b3c4d5"
down_revision: str | None = "d9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_activation_inbound_cursors",
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("last_update_id", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("bot_id"),
    )
    op.create_table(
        "telegram_activation_send_ledger",
        sa.Column("ledger_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("transport_message_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("ledger_id"),
        sa.UniqueConstraint(
            "bot_id",
            "idempotency_key",
            name="uq_tg_activation_send_bot_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("telegram_activation_send_ledger")
    op.drop_table("telegram_activation_inbound_cursors")
