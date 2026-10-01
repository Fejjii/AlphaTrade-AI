"""Durable Strategy Brain setup and event projections.

Revision ID: a1brain001
Revises: f1a2b3c4d5e6
"""

import sqlalchemy as sa
from alembic import op

revision = "a1brain001"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "strategy_brain_setups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), sa.ForeignKey("user_strategies.id"), nullable=False),
        sa.Column(
            "strategy_version_id",
            sa.Uuid(),
            sa.ForeignKey("user_strategy_versions.id"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("candidate_id", sa.Uuid()),
        sa.Column("assessment_id", sa.Uuid()),
        sa.Column("decision_id", sa.Uuid()),
        sa.Column("journal_trade_id", sa.Uuid()),
    )
    op.create_index(
        "ix_brain_org_symbol_time",
        "strategy_brain_setups",
        ["organization_id", "symbol", "observed_at"],
    )
    op.create_table(
        "strategy_brain_setup_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("setup_id", sa.Uuid(), sa.ForeignKey("strategy_brain_setups.id"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )

    op.create_index(
        "ix_brain_event_setup_time",
        "strategy_brain_setup_events",
        ["organization_id", "setup_id", "occurred_at"],
    )


def downgrade():
    op.drop_index("ix_brain_event_setup_time", table_name="strategy_brain_setup_events")
    op.drop_table("strategy_brain_setup_events")
    op.drop_index("ix_brain_org_symbol_time", table_name="strategy_brain_setups")
    op.drop_table("strategy_brain_setups")
