"""Slice 78 — paper validation drafts from reviewed setup alerts."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "z6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_validation_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_alert_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=True),
        sa.Column("timeframe", sa.String(length=10), nullable=True),
        sa.Column("condition", sa.String(length=64), nullable=True),
        sa.Column("direction", sa.String(length=10), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("trigger_level", sa.Float(), nullable=True),
        sa.Column("invalidation_level", sa.Float(), nullable=True),
        sa.Column("latest_price", sa.Float(), nullable=True),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("user_notes", sa.Text(), nullable=True),
        sa.Column("risk_mode", sa.String(length=20), nullable=False, server_default="conservative"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["source_alert_id"], ["paper_validation_alerts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "source_alert_id",
            "status",
            name="uq_paper_validation_drafts_org_alert_status",
        ),
    )
    op.create_index(
        "ix_paper_validation_drafts_org_status",
        "paper_validation_drafts",
        ["organization_id", "status"],
    )
    op.create_index(
        op.f("ix_paper_validation_drafts_source_alert_id"),
        "paper_validation_drafts",
        ["source_alert_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_paper_validation_drafts_source_alert_id"))
    op.drop_index("ix_paper_validation_drafts_org_status")
    op.drop_table("paper_validation_drafts")
