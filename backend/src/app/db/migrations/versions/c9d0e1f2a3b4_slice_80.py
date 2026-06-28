"""Slice 80 — paper validation candidates from ready drafts."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_validation_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("source_alert_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=True),
        sa.Column("timeframe", sa.String(length=10), nullable=True),
        sa.Column("condition", sa.String(length=64), nullable=True),
        sa.Column("direction", sa.String(length=10), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("trigger_level", sa.Float(), nullable=True),
        sa.Column("invalidation_level", sa.Float(), nullable=True),
        sa.Column("latest_price", sa.Float(), nullable=True),
        sa.Column("thesis", sa.Text(), nullable=True),
        sa.Column("entry_criteria", sa.Text(), nullable=True),
        sa.Column("invalidation_criteria", sa.Text(), nullable=True),
        sa.Column("risk_notes", sa.Text(), nullable=True),
        sa.Column("checklist_snapshot", sa.JSON(), nullable=True),
        sa.Column("risk_mode", sa.String(length=20), nullable=False, server_default="conservative"),
        sa.Column(
            "candidate_status",
            sa.String(length=20),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["paper_validation_drafts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["source_alert_id"], ["paper_validation_alerts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_paper_validation_candidates_org_status",
        "paper_validation_candidates",
        ["organization_id", "candidate_status"],
    )
    op.create_index(
        op.f("ix_paper_validation_candidates_draft_id"),
        "paper_validation_candidates",
        ["draft_id"],
    )
    op.create_index(
        "ix_paper_validation_candidates_org_draft_active",
        "paper_validation_candidates",
        ["organization_id", "draft_id"],
        unique=True,
        sqlite_where=sa.text("candidate_status IN ('queued', 'reviewing')"),
        postgresql_where=sa.text("candidate_status IN ('queued', 'reviewing')"),
    )


def downgrade() -> None:
    op.drop_index("ix_paper_validation_candidates_org_draft_active")
    op.drop_index(op.f("ix_paper_validation_candidates_draft_id"))
    op.drop_index("ix_paper_validation_candidates_org_status")
    op.drop_table("paper_validation_candidates")
