"""durable setup lifetime pins

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-09-21 11:50:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "setup_lifetime_pins",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=False),
        sa.Column("compiled_setup_definition_id", sa.Uuid(), nullable=False),
        sa.Column("compiled_content_hash", sa.String(length=64), nullable=False),
        sa.Column("trigger_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trigger_bar_hash", sa.String(length=64), nullable=False),
        sa.Column("expired", sa.Boolean(), nullable=False),
        sa.Column("required_lineage_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "length(compiled_content_hash) = 64",
            name="ck_setup_lifetime_pins_setup_lifetime_compiled_hash_len",
        ),
        sa.CheckConstraint(
            "length(trigger_bar_hash) = 64",
            name="ck_setup_lifetime_pins_setup_lifetime_trigger_hash_len",
        ),
        sa.CheckConstraint(
            "length(required_lineage_hash) = 64",
            name="ck_setup_lifetime_pins_setup_lifetime_lineage_hash_len",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "symbol",
            "timeframe",
            "strategy_version_id",
            "compiled_setup_definition_id",
            "compiled_content_hash",
            name="uq_setup_lifetime_semantic_key",
        ),
    )
    op.create_index(
        "ix_setup_lifetime_pins_org_symbol_timeframe",
        "setup_lifetime_pins",
        ["organization_id", "symbol", "timeframe"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_setup_lifetime_pins_org_symbol_timeframe",
        table_name="setup_lifetime_pins",
    )
    op.drop_table("setup_lifetime_pins")
