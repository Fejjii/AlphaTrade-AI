"""AT-033 — journal completion (import, backfill, attachments, entry method).

Adds:
- partial unique index on (organization_id, external_ref) for idempotent
  import/backfill deduplication (NULL refs stay unconstrained);
- ``entry_method`` column on journal_trades (human-vs-system analytics);
- ``journal_import_batches`` (reconciliation history for bulk imports);
- ``journal_trade_attachments`` (DB-backed binary evidence storage).

Record-only journal layer; no execution-path change. The unique index will
fail loudly if duplicate (organization_id, external_ref) rows pre-exist —
none are expected because no import path existed before AT-033.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "l8a9b0c1d2e3"
down_revision = "k7f8a9b0c1d2"
branch_labels = None
depends_on = None

_ENTRY_METHOD_ENUM = sa.Enum(
    "MANUAL",
    "AUTO",
    "IMPORT",
    "BACKFILL",
    name="journalentrymethod",
    native_enum=False,
    length=40,
)
_IMPORT_BATCH_STATUS_ENUM = sa.Enum(
    "DRY_RUN",
    "COMMITTED",
    "FAILED",
    name="journalimportbatchstatus",
    native_enum=False,
    length=40,
)


def upgrade() -> None:
    op.add_column(
        "journal_trades",
        sa.Column(
            "entry_method",
            _ENTRY_METHOD_ENUM,
            nullable=False,
            server_default="MANUAL",
        ),
    )
    op.create_index(
        "uq_journal_trades_org_external_ref",
        "journal_trades",
        ["organization_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text("external_ref IS NOT NULL"),
        sqlite_where=sa.text("external_ref IS NOT NULL"),
    )

    op.create_table(
        "journal_import_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", _IMPORT_BATCH_STATUS_ENUM, nullable=False),
        sa.Column("source_label", sa.String(length=120), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("invalid_count", sa.Integer(), nullable=False),
        sa.Column("row_report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_journal_import_batches_organization_id"),
        "journal_import_batches",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_journal_import_batches_user_id"),
        "journal_import_batches",
        ["user_id"],
    )

    op.create_table(
        "journal_trade_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("journal_trade_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_backend", sa.String(length=20), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["journal_trade_id"], ["journal_trades.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_journal_trade_attachments_journal_trade_id"),
        "journal_trade_attachments",
        ["journal_trade_id"],
    )
    op.create_index(
        op.f("ix_journal_trade_attachments_organization_id"),
        "journal_trade_attachments",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_journal_trade_attachments_organization_id"),
        table_name="journal_trade_attachments",
    )
    op.drop_index(
        op.f("ix_journal_trade_attachments_journal_trade_id"),
        table_name="journal_trade_attachments",
    )
    op.drop_table("journal_trade_attachments")
    op.drop_index(
        op.f("ix_journal_import_batches_user_id"),
        table_name="journal_import_batches",
    )
    op.drop_index(
        op.f("ix_journal_import_batches_organization_id"),
        table_name="journal_import_batches",
    )
    op.drop_table("journal_import_batches")
    op.drop_index("uq_journal_trades_org_external_ref", table_name="journal_trades")
    op.drop_column("journal_trades", "entry_method")
