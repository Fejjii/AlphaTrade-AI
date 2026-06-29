"""Slice 82 — manual paper validation run sessions from planned run plans."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_validation_run_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("run_plan_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("source_alert_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=True),
        sa.Column("timeframe", sa.String(length=10), nullable=True),
        sa.Column("condition", sa.String(length=64), nullable=True),
        sa.Column("direction", sa.String(length=10), nullable=True),
        sa.Column("risk_mode", sa.String(length=20), nullable=False, server_default="conservative"),
        sa.Column("validation_window", sa.String(length=32), nullable=True),
        sa.Column("observation_timeframe", sa.String(length=10), nullable=True),
        sa.Column("max_duration_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "session_status",
            sa.String(length=20),
            nullable=False,
            server_default="running",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("started_by", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["paper_validation_candidates.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["paper_validation_drafts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["run_plan_id"], ["paper_validation_run_plans.id"]),
        sa.ForeignKeyConstraint(["source_alert_id"], ["paper_validation_alerts.id"]),
        sa.ForeignKeyConstraint(["started_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_paper_validation_run_sessions_org_status",
        "paper_validation_run_sessions",
        ["organization_id", "session_status"],
    )
    op.create_index(
        op.f("ix_paper_validation_run_sessions_run_plan_id"),
        "paper_validation_run_sessions",
        ["run_plan_id"],
    )
    op.create_index(
        op.f("ix_paper_validation_run_sessions_organization_id"),
        "paper_validation_run_sessions",
        ["organization_id"],
    )
    op.create_index(
        "ix_pv_run_sessions_org_plan_active",
        "paper_validation_run_sessions",
        ["organization_id", "run_plan_id"],
        unique=True,
        sqlite_where=sa.text("session_status = 'running'"),
        postgresql_where=sa.text("session_status = 'running'"),
    )


def downgrade() -> None:
    op.drop_index("ix_pv_run_sessions_org_plan_active")
    op.drop_index(op.f("ix_paper_validation_run_sessions_organization_id"))
    op.drop_index(op.f("ix_paper_validation_run_sessions_run_plan_id"))
    op.drop_index("ix_paper_validation_run_sessions_org_status")
    op.drop_table("paper_validation_run_sessions")
