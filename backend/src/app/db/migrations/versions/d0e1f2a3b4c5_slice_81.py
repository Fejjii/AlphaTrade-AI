"""Slice 81 — paper validation run plans from reviewing candidates."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_validation_run_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
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
            "plan_status",
            sa.String(length=20),
            nullable=False,
            server_default="planned",
        ),
        sa.Column("validation_window", sa.String(length=32), nullable=True),
        sa.Column("observation_timeframe", sa.String(length=10), nullable=True),
        sa.Column("max_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("planned_entry_rule", sa.Text(), nullable=True),
        sa.Column("planned_invalidation_rule", sa.Text(), nullable=True),
        sa.Column("planned_success_criteria", sa.Text(), nullable=True),
        sa.Column("planned_failure_criteria", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["paper_validation_candidates.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["paper_validation_drafts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["source_alert_id"], ["paper_validation_alerts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_paper_validation_run_plans_org_status",
        "paper_validation_run_plans",
        ["organization_id", "plan_status"],
    )
    op.create_index(
        op.f("ix_paper_validation_run_plans_candidate_id"),
        "paper_validation_run_plans",
        ["candidate_id"],
    )
    op.create_index(
        "ix_paper_validation_run_plans_org_candidate_active",
        "paper_validation_run_plans",
        ["organization_id", "candidate_id"],
        unique=True,
        sqlite_where=sa.text("plan_status IN ('planned', 'needs_revision')"),
        postgresql_where=sa.text("plan_status IN ('planned', 'needs_revision')"),
    )


def downgrade() -> None:
    op.drop_index("ix_paper_validation_run_plans_org_candidate_active")
    op.drop_index(op.f("ix_paper_validation_run_plans_candidate_id"))
    op.drop_index("ix_paper_validation_run_plans_org_status")
    op.drop_table("paper_validation_run_plans")
