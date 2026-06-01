"""Workflows slice 13 — watchlist and workflow metadata extensions.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-01

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist_items",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("exchange", sa.String(length=40), nullable=False),
        sa.Column("timeframes", sa.JSON(), nullable=False),
        sa.Column("strategy_ids", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_watchlist_items_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_watchlist_items_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watchlist_items")),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            "symbol",
            "exchange",
            name="uq_watchlist_org_user_symbol_exchange",
        ),
    )

    op.add_column("trade_proposals", sa.Column("entry_low", sa.Numeric(20, 8), nullable=True))
    op.add_column("trade_proposals", sa.Column("entry_high", sa.Numeric(20, 8), nullable=True))
    op.add_column(
        "trade_proposals",
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column("trade_proposals", sa.Column("risk_result", sa.JSON(), nullable=True))

    op.add_column("positions", sa.Column("take_profits", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("positions", sa.Column("risk_state", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("positions", "risk_state")
    op.drop_column("positions", "take_profits")
    op.drop_column("trade_proposals", "risk_result")
    op.drop_column("trade_proposals", "approval_required")
    op.drop_column("trade_proposals", "entry_high")
    op.drop_column("trade_proposals", "entry_low")
    op.drop_table("watchlist_items")
