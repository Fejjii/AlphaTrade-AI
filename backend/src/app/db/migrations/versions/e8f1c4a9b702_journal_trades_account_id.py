"""add nullable account_id on journal_trades

Revision ID: e8f1c4a9b702
Revises: d4f7a2c8e901
Create Date: 2026-09-20 15:22:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8f1c4a9b702"
down_revision: str | None = "d4f7a2c8e901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("journal_trades", sa.Column("account_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_journal_trades_account_id"),
        "journal_trades",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_journal_trades_account_id"), table_name="journal_trades")
    op.drop_column("journal_trades", "account_id")
