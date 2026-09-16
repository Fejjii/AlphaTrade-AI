"""phase 4 canonical journal uniqueness, venue corrections, projection receipts

Revision ID: 9b0c1d2e3f4a
Revises: 8a9b0c1d2e3f
Create Date: 2026-09-16 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.historical_immutability import historical_immutability_phase4_install_statements

revision: str = "9b0c1d2e3f4a"
down_revision: str | None = "8a9b0c1d2e3f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)
_OLD_OBSERVATION_ENUM = sa.Enum(
    "BEHAVIORAL",
    "EMOTIONAL",
    "EXECUTION",
    "MARKET",
    "RISK",
    "PROCESS",
    name="journalobservationcategory",
    native_enum=False,
    length=40,
)
_NEW_OBSERVATION_ENUM = sa.Enum(
    "BEHAVIORAL",
    "EMOTIONAL",
    "EXECUTION",
    "MARKET",
    "RISK",
    "PROCESS",
    "MISTAKE",
    "DISCIPLINE",
    "LESSON",
    name="journalobservationcategory",
    native_enum=False,
    length=40,
)


def _widen_observation_category() -> None:
    bind = op.get_bind()
    allowed = ", ".join(
        f"'{value}'"
        for value in (
            "BEHAVIORAL",
            "EMOTIONAL",
            "EXECUTION",
            "MARKET",
            "RISK",
            "PROCESS",
            "MISTAKE",
            "DISCIPLINE",
            "LESSON",
        )
    )
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE journal_trade_observations "
            "DROP CONSTRAINT IF EXISTS journalobservationcategory"
        )
        op.execute(
            "ALTER TABLE journal_trade_observations "
            f"ADD CONSTRAINT journalobservationcategory CHECK (category IN ({allowed}))"
        )
        return
    with op.batch_alter_table("journal_trade_observations") as batch:
        batch.alter_column(
            "category",
            existing_type=_OLD_OBSERVATION_ENUM,
            type_=_NEW_OBSERVATION_ENUM,
            existing_nullable=False,
        )


def upgrade() -> None:
    op.add_column("journal_trades", sa.Column("execution_lifecycle_id", sa.Uuid(), nullable=True))
    op.create_index(
        "ix_journal_trades_execution_lifecycle_id",
        "journal_trades",
        ["execution_lifecycle_id"],
    )
    op.create_index(
        "uq_journal_trades_org_lifecycle",
        "journal_trades",
        ["organization_id", "execution_lifecycle_id"],
        unique=True,
        postgresql_where=sa.text("execution_lifecycle_id IS NOT NULL"),
        sqlite_where=sa.text("execution_lifecycle_id IS NOT NULL"),
    )

    op.create_table(
        "journal_lifecycle_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("execution_lifecycle_id", sa.Uuid(), nullable=True),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("source_aggregate", sa.String(length=160), nullable=False),
        sa.Column("source_event_id", sa.String(length=160), nullable=False),
        sa.Column("source_event_version", sa.Integer(), nullable=False),
        sa.Column("supersession", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("journal_trade_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["journal_trade_id"], ["journal_trades.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_journal_lifecycle_events"),
        sa.UniqueConstraint(
            "organization_id",
            "source_system",
            "source_aggregate",
            "event_type",
            "source_event_id",
            "source_event_version",
            "supersession",
            name="uq_journal_lifecycle_event_source",
        ),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_journal_lifecycle_event_hash"),
    )
    op.create_index(
        "ix_journal_lifecycle_events_organization_id",
        "journal_lifecycle_events",
        ["organization_id"],
    )
    op.create_index(
        "ix_journal_lifecycle_org_lifecycle",
        "journal_lifecycle_events",
        ["organization_id", "execution_lifecycle_id"],
    )

    op.create_table(
        "journal_projection_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("execution_lifecycle_id", sa.Uuid(), nullable=True),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("source_aggregate", sa.String(length=160), nullable=False),
        sa.Column("source_event_id", sa.String(length=160), nullable=False),
        sa.Column("source_event_version", sa.Integer(), nullable=False),
        sa.Column("supersession", sa.Integer(), nullable=False),
        sa.Column("journal_trade_id", sa.Uuid(), nullable=True),
        sa.Column("created_journal_trade", sa.Boolean(), nullable=False),
        sa.Column("skipped_reason", sa.String(length=80), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["journal_trade_id"], ["journal_trades.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_journal_projection_receipts"),
        sa.UniqueConstraint(
            "organization_id",
            "source_system",
            "source_aggregate",
            "event_type",
            "source_event_id",
            "source_event_version",
            "supersession",
            name="uq_journal_projection_receipt_source",
        ),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_journal_projection_receipt_hash"),
    )
    op.create_index(
        "ix_journal_projection_receipts_organization_id",
        "journal_projection_receipts",
        ["organization_id"],
    )

    op.create_table(
        "journal_trade_venue_corrections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("journal_trade_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column("previous_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["journal_trade_id"], ["journal_trades.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_journal_trade_venue_corrections"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_journal_venue_correction_hash"),
    )
    op.create_index(
        "ix_journal_trade_venue_corrections_journal_trade_id",
        "journal_trade_venue_corrections",
        ["journal_trade_id"],
    )
    op.create_index(
        "ix_journal_trade_venue_corrections_organization_id",
        "journal_trade_venue_corrections",
        ["organization_id"],
    )
    op.create_index(
        "ix_journal_venue_correction_trade",
        "journal_trade_venue_corrections",
        ["organization_id", "journal_trade_id"],
    )

    _widen_observation_category()

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for statement in historical_immutability_phase4_install_statements():
            op.execute(statement)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_journal_trade_venue_corrections_immutable "
            "ON journal_trade_venue_corrections"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_journal_projection_receipts_immutable "
            "ON journal_projection_receipts"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_journal_lifecycle_events_immutable "
            "ON journal_lifecycle_events"
        )

    op.drop_index(
        "ix_journal_venue_correction_trade",
        table_name="journal_trade_venue_corrections",
    )
    op.drop_index(
        "ix_journal_trade_venue_corrections_organization_id",
        table_name="journal_trade_venue_corrections",
    )
    op.drop_index(
        "ix_journal_trade_venue_corrections_journal_trade_id",
        table_name="journal_trade_venue_corrections",
    )
    op.drop_table("journal_trade_venue_corrections")
    op.drop_index(
        "ix_journal_projection_receipts_organization_id",
        table_name="journal_projection_receipts",
    )
    op.drop_table("journal_projection_receipts")
    op.drop_index("ix_journal_lifecycle_org_lifecycle", table_name="journal_lifecycle_events")
    op.drop_index(
        "ix_journal_lifecycle_events_organization_id",
        table_name="journal_lifecycle_events",
    )
    op.drop_table("journal_lifecycle_events")
    op.drop_index("uq_journal_trades_org_lifecycle", table_name="journal_trades")
    op.drop_index("ix_journal_trades_execution_lifecycle_id", table_name="journal_trades")
    op.drop_column("journal_trades", "execution_lifecycle_id")
