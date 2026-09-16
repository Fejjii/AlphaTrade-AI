"""phase 1 fill facts, transition price, and historical immutability

Revision ID: 5c8e4a71b9d2
Revises: 4f0a2c9b71e8
Create Date: 2026-09-15 21:45:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.historical_immutability import (
    historical_immutability_install_statements,
    historical_immutability_uninstall_statements,
)

revision: str = "5c8e4a71b9d2"
down_revision: str | None = "4f0a2c9b71e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column(
        "execution_transitions",
        sa.Column("unit_price", sa.Numeric(20, 8), nullable=True),
    )
    op.add_column(
        "risk_reservations",
        sa.Column(
            "converted_trade_slots",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_table(
        "execution_fill_facts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("venue_source", sa.String(length=80), nullable=False),
        sa.Column("source_fill_identity", sa.String(length=128), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", _TS, nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            _TS,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            _TS,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("price > 0", name="ck_execution_fill_fact_price"),
        sa.CheckConstraint("quantity > 0", name="ck_execution_fill_fact_quantity"),
        sa.CheckConstraint(
            "length(content_hash) = 64",
            name="ck_execution_fill_fact_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["command_id"],
            ["execution_commands.id"],
            name="fk_execution_fill_fact_command",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["execution_receipts.id"],
            name="fk_execution_fill_fact_receipt",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "receipt_id",
            "source_fill_identity",
            name="uq_execution_fill_fact_source",
        ),
    )
    op.create_index(
        "ix_execution_fill_facts_receipt",
        "execution_fill_facts",
        ["receipt_id"],
    )
    for statement in historical_immutability_install_statements():
        op.execute(statement)


def downgrade() -> None:
    for statement in historical_immutability_uninstall_statements():
        op.execute(statement)
    op.drop_index("ix_execution_fill_facts_receipt", table_name="execution_fill_facts")
    op.drop_table("execution_fill_facts")
    op.drop_column("risk_reservations", "converted_trade_slots")
    op.drop_column("execution_transitions", "unit_price")
