"""Slice 61 — BloFin demo execution: exchange orders and fills."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("internal_order_id", sa.Uuid(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("exchange", sa.String(length=40), nullable=False),
        sa.Column("exchange_mode", sa.String(length=32), nullable=False),
        sa.Column("inst_id", sa.String(length=40), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("order_type", sa.String(length=16), nullable=False),
        sa.Column("size", sa.Numeric(20, 8), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=True),
        sa.Column("exchange_order_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="submitted"),
        sa.Column("filled_size", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("average_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["internal_order_id"],
            ["orders.id"],
            name=op.f("fk_exchange_orders_internal_order_id_orders"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_exchange_orders_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exchange_orders")),
    )

    op.create_table(
        "exchange_fills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("exchange_order_id", sa.Uuid(), nullable=False),
        sa.Column("fill_id", sa.String(length=64), nullable=True),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("size", sa.Numeric(20, 8), nullable=False),
        sa.Column("fee", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("fee_currency", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["exchange_order_id"],
            ["exchange_orders.id"],
            name=op.f("fk_exchange_fills_exchange_order_id_exchange_orders"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exchange_fills")),
    )


def downgrade() -> None:
    op.drop_table("exchange_fills")
    op.drop_table("exchange_orders")
