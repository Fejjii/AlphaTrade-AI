"""Slice 40 — paper validation scheduler, observability, alerts."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "r8s9t0u1v2w3"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_validation_scheduler_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), server_default="300", nullable=False),
        sa.Column("max_runs_per_cycle", sa.Integer(), server_default="5", nullable=False),
        sa.Column("max_scans_per_minute", sa.Integer(), server_default="10", nullable=False),
        sa.Column("last_tick_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_tick_status", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_paper_scheduler_org"),
    )
    op.create_table(
        "paper_validation_runtime_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("strategy_id", sa.Uuid(), nullable=True),
        sa.Column("symbol", sa.String(length=30), nullable=True),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("signals_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("trades_opened", sa.Integer(), server_default="0", nullable=False),
        sa.Column("trades_closed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("blockers", sa.JSON(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("data_freshness", sa.String(length=40), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["paper_validation_runs.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["user_strategies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "paper_validation_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("alert_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=40), server_default="info", nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=True),
        sa.Column("paper_validation_run_id", sa.Uuid(), nullable=True),
        sa.Column("paper_trade_id", sa.Uuid(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["paper_trade_id"], ["paper_trades.id"]),
        sa.ForeignKeyConstraint(["paper_validation_run_id"], ["paper_validation_runs.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["user_strategies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "paper_validation_observability_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("strategy_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["paper_validation_runs.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["user_strategies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "paper_validation_sample_windows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paper_validation_run_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trades_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("win_rate", sa.Float(), server_default="0", nullable=False),
        sa.Column("net_pnl", sa.Numeric(20, 8), server_default="0", nullable=False),
        sa.Column("max_drawdown", sa.Float(), server_default="0", nullable=False),
        sa.Column("expectancy", sa.Numeric(20, 8), server_default="0", nullable=False),
        sa.Column("recommendation", sa.String(length=40), nullable=True),
        sa.Column("data_quality", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["paper_validation_run_id"], ["paper_validation_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("paper_validation_sample_windows")
    op.drop_table("paper_validation_observability_events")
    op.drop_table("paper_validation_alerts")
    op.drop_table("paper_validation_runtime_history")
    op.drop_table("paper_validation_scheduler_configs")
