"""Slice 42 — market watcher bridge decisions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "u1v2w3x4y5z6"
down_revision = "t0u1v2w3x4y5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_watcher_bridge_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=True),
        sa.Column("strategy_id", sa.Uuid(), nullable=True),
        sa.Column("paper_validation_run_id", sa.Uuid(), nullable=True),
        sa.Column("symbol", sa.String(length=30), nullable=True),
        sa.Column("exchange", sa.String(length=40), nullable=True),
        sa.Column("timeframe", sa.String(length=10), nullable=True),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("blockers", sa.JSON(), nullable=True),
        sa.Column("triggered_scan_id", sa.Uuid(), nullable=True),
        sa.Column("created_alert_id", sa.Uuid(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_alert_id"], ["paper_validation_alerts.id"]),
        sa.ForeignKeyConstraint(["observation_id"], ["market_watcher_observations.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["paper_validation_run_id"], ["paper_validation_runs.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["user_strategies.id"]),
        sa.ForeignKeyConstraint(["triggered_scan_id"], ["paper_signals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_watcher_bridge_decisions_org_created",
        "market_watcher_bridge_decisions",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_watcher_bridge_decisions_org_created")
    op.drop_table("market_watcher_bridge_decisions")
