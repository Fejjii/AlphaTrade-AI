"""Slice 83 — paper validation session observations and results."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_validation_session_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("run_session_id", sa.Uuid(), nullable=False),
        sa.Column("run_plan_id", sa.Uuid(), nullable=False),
        sa.Column("observation_kind", sa.String(length=32), nullable=False),
        sa.Column("observed_price", sa.Float(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["run_plan_id"], ["paper_validation_run_plans.id"]),
        sa.ForeignKeyConstraint(["run_session_id"], ["paper_validation_run_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pv_session_observations_org_session",
        "paper_validation_session_observations",
        ["organization_id", "run_session_id"],
    )
    op.create_index(
        op.f("ix_paper_validation_session_observations_organization_id"),
        "paper_validation_session_observations",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_paper_validation_session_observations_run_session_id"),
        "paper_validation_session_observations",
        ["run_session_id"],
    )

    op.create_table(
        "paper_validation_session_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("run_session_id", sa.Uuid(), nullable=False),
        sa.Column("run_plan_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("success_criteria_met", sa.String(length=16), nullable=False),
        sa.Column("success_criteria_notes", sa.Text(), nullable=True),
        sa.Column("failure_criteria_met", sa.String(length=16), nullable=False),
        sa.Column("failure_criteria_notes", sa.Text(), nullable=True),
        sa.Column(
            "invalidation_hit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("invalidation_notes", sa.Text(), nullable=True),
        sa.Column("entry_assessment", sa.String(length=32), nullable=False),
        sa.Column("discipline_assessment", sa.String(length=32), nullable=False),
        sa.Column("behaved_as_expected", sa.Boolean(), nullable=True),
        sa.Column("lessons", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["run_plan_id"], ["paper_validation_run_plans.id"]),
        sa.ForeignKeyConstraint(["run_session_id"], ["paper_validation_run_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_paper_validation_session_results_organization_id"),
        "paper_validation_session_results",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_paper_validation_session_results_run_session_id"),
        "paper_validation_session_results",
        ["run_session_id"],
    )
    op.create_index(
        "ix_pv_session_results_org_session_unique",
        "paper_validation_session_results",
        ["organization_id", "run_session_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_pv_session_results_org_session_unique")
    op.drop_index(op.f("ix_paper_validation_session_results_run_session_id"))
    op.drop_index(op.f("ix_paper_validation_session_results_organization_id"))
    op.drop_table("paper_validation_session_results")
    op.drop_index(op.f("ix_paper_validation_session_observations_run_session_id"))
    op.drop_index(op.f("ix_paper_validation_session_observations_organization_id"))
    op.drop_index("ix_pv_session_observations_org_session")
    op.drop_table("paper_validation_session_observations")
