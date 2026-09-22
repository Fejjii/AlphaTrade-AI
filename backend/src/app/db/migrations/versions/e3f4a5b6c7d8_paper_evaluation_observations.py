"""paper evaluation observation persistence

Revision ID: e3f4a5b6c7d8
Revises: c8d9e0f1a2b3
Create Date: 2026-09-21 21:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: str | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_evaluation_observations",
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("source_event_id", sa.String(length=160), nullable=False),
        sa.Column("source_event_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=True),
        sa.Column("setup_definition_id", sa.Uuid(), nullable=True),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("assessment_id", sa.Uuid(), nullable=True),
        sa.Column("journal_trade_id", sa.Uuid(), nullable=True),
        sa.Column("scan_status", sa.String(length=64), nullable=True),
        sa.Column("reason_code", sa.String(length=128), nullable=True),
        sa.Column("assessment_state", sa.String(length=32), nullable=True),
        sa.Column("eligibility_state", sa.String(length=32), nullable=True),
        sa.Column("data_quality", sa.String(length=32), nullable=False),
        sa.Column("replayed", sa.Boolean(), nullable=False),
        sa.Column("plan_approved", sa.Boolean(), nullable=False),
        sa.Column("rejected", sa.Boolean(), nullable=False),
        sa.Column("skipped", sa.Boolean(), nullable=False),
        sa.Column("filled", sa.Boolean(), nullable=False),
        sa.Column("closed", sa.Boolean(), nullable=False),
        sa.Column("executed_outcome", sa.Boolean(), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=True),
        sa.Column("net_pnl", sa.Numeric(20, 8), nullable=True),
        sa.Column("mfe_amount", sa.Numeric(20, 8), nullable=True),
        sa.Column("mae_amount", sa.Numeric(20, 8), nullable=True),
        sa.Column("capture_pct", sa.Numeric(20, 8), nullable=True),
        sa.Column("planned_risk_amount", sa.Numeric(20, 8), nullable=True),
        sa.Column("setup_quality", sa.String(length=32), nullable=True),
        sa.Column("execution_quality", sa.String(length=32), nullable=True),
        sa.Column("risk_adherence", sa.String(length=32), nullable=True),
        sa.Column("trader_behavior", sa.String(length=32), nullable=True),
        sa.Column("rule_compliance", sa.String(length=32), nullable=True),
        sa.Column("learning_venue_mode", sa.String(length=32), nullable=False),
        sa.Column("live_executable", sa.Boolean(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("narrative_explanation", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "length(content_hash) = 64",
            name="ck_paper_evaluation_observations_paper_evaluation_observations_hash_len",
        ),
        sa.CheckConstraint(
            "source_event_version >= 1",
            name="ck_paper_evaluation_observations_paper_evaluation_observations_version_min",
        ),
        sa.PrimaryKeyConstraint("observation_id", name="pk_paper_evaluation_observations"),
        sa.UniqueConstraint(
            "organization_id",
            "source_system",
            "source_event_id",
            "source_event_version",
            name="uq_paper_evaluation_observations_source",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "observation_id",
            name="uq_paper_evaluation_observations_org_id",
        ),
    )
    op.create_index(
        "ix_paper_evaluation_observations_org_stage",
        "paper_evaluation_observations",
        ["organization_id", "stage", "occurred_at"],
    )
    op.create_index(
        "ix_paper_evaluation_observations_org_candidate",
        "paper_evaluation_observations",
        ["organization_id", "candidate_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_paper_evaluation_observations_org_candidate",
        table_name="paper_evaluation_observations",
    )
    op.drop_index(
        "ix_paper_evaluation_observations_org_stage",
        table_name="paper_evaluation_observations",
    )
    op.drop_table("paper_evaluation_observations")
