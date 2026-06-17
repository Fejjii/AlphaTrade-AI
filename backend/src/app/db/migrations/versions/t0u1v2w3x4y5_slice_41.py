"""Slice 41 — alert delivery fields and market watcher observations."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "t0u1v2w3x4y5"
down_revision = "s9t0u1v2w3x4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "paper_validation_alerts",
        sa.Column(
            "delivery_status",
            sa.String(length=40),
            nullable=False,
            server_default="disabled",
        ),
    )
    op.add_column(
        "paper_validation_alerts",
        sa.Column(
            "delivery_channel",
            sa.String(length=40),
            nullable=False,
            server_default="in_app",
        ),
    )
    op.add_column(
        "paper_validation_alerts",
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "paper_validation_alerts",
        sa.Column("last_delivery_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "paper_validation_alerts",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "paper_validation_alerts",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_paper_validation_alerts_delivery_status",
        "paper_validation_alerts",
        ["organization_id", "delivery_status"],
    )

    op.create_table(
        "market_watcher_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("exchange", sa.String(length=40), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("volume", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("data_freshness", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("related_strategy_id", sa.Uuid(), nullable=True),
        sa.Column("related_paper_validation_run_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_alert_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["created_alert_id"], ["paper_validation_alerts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["related_paper_validation_run_id"], ["paper_validation_runs.id"]),
        sa.ForeignKeyConstraint(["related_strategy_id"], ["user_strategies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_watcher_observations_org_observed",
        "market_watcher_observations",
        ["organization_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_watcher_observations_org_observed")
    op.drop_table("market_watcher_observations")
    op.drop_index("ix_paper_validation_alerts_delivery_status")
    op.drop_column("paper_validation_alerts", "next_retry_at")
    op.drop_column("paper_validation_alerts", "delivered_at")
    op.drop_column("paper_validation_alerts", "last_delivery_error")
    op.drop_column("paper_validation_alerts", "delivery_attempts")
    op.drop_column("paper_validation_alerts", "delivery_channel")
    op.drop_column("paper_validation_alerts", "delivery_status")
