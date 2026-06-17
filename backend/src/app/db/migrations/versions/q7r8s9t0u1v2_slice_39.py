"""Slice 39 — paper validation runtime loop."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "q7r8s9t0u1v2"
down_revision = "p6q7r8s9t0u1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "paper_validation_runs",
        sa.Column("strategy_version_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "paper_validation_runs",
        sa.Column("runtime_mode", sa.String(length=40), server_default="scan_only", nullable=False),
    )
    op.add_column("paper_validation_runs", sa.Column("config", sa.JSON(), nullable=True))
    op.add_column("paper_validation_runs", sa.Column("blockers", sa.JSON(), nullable=True))
    op.add_column(
        "paper_validation_runs",
        sa.Column("last_scan_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "paper_validation_runs",
        sa.Column("last_tick_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("paper_validation_runs", sa.Column("last_scan_result", sa.JSON(), nullable=True))
    op.create_foreign_key(
        "fk_paper_validation_runs_strategy_version_id",
        "paper_validation_runs",
        "user_strategy_versions",
        ["strategy_version_id"],
        ["id"],
    )

    op.create_table(
        "paper_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("paper_validation_run_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("exchange", sa.String(length=40), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("direction", sa.String(length=40), nullable=False),
        sa.Column("triggered", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=40), server_default="detected", nullable=False),
        sa.Column("matched_entry_blocks", sa.JSON(), nullable=True),
        sa.Column("blocked_no_trade_filters", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("suggested_entry", sa.Numeric(20, 8), nullable=True),
        sa.Column("stop_loss", sa.Numeric(20, 8), nullable=True),
        sa.Column("invalidation", sa.Text(), nullable=True),
        sa.Column("tp_plan", sa.JSON(), nullable=True),
        sa.Column("runner_plan", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("limitations", sa.JSON(), nullable=True),
        sa.Column("rule_engine_source", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["paper_validation_run_id"], ["paper_validation_runs.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["user_strategies.id"]),
        sa.ForeignKeyConstraint(["strategy_version_id"], ["user_strategy_versions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "paper_trades",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("paper_validation_run_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_from_signal_id", sa.Uuid(), nullable=True),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("exchange", sa.String(length=40), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("direction", sa.String(length=40), nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("size", sa.Numeric(20, 8), nullable=True),
        sa.Column("stop_loss", sa.Numeric(20, 8), nullable=True),
        sa.Column("invalidation", sa.Text(), nullable=True),
        sa.Column("tp_plan", sa.JSON(), nullable=True),
        sa.Column("runner_plan", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=40), server_default="proposed", nullable=False),
        sa.Column("exit_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_reason", sa.String(length=60), nullable=True),
        sa.Column("gross_pnl", sa.Numeric(20, 8), nullable=True),
        sa.Column("net_pnl", sa.Numeric(20, 8), nullable=True),
        sa.Column("fees", sa.Numeric(20, 8), nullable=True),
        sa.Column("slippage", sa.Numeric(20, 8), nullable=True),
        sa.Column("rule_engine_source", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_from_signal_id"], ["paper_signals.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["paper_validation_run_id"], ["paper_validation_runs.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["user_strategies.id"]),
        sa.ForeignKeyConstraint(["strategy_version_id"], ["user_strategy_versions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "paper_trade_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("paper_trade_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["paper_trade_id"], ["paper_trades.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "paper_validation_metric_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("paper_validation_run_id", sa.Uuid(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("trigger_trade_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["paper_validation_run_id"], ["paper_validation_runs.id"]),
        sa.ForeignKeyConstraint(["trigger_trade_id"], ["paper_trades.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("paper_validation_metric_snapshots")
    op.drop_table("paper_trade_events")
    op.drop_table("paper_trades")
    op.drop_table("paper_signals")
    op.drop_constraint(
        "fk_paper_validation_runs_strategy_version_id",
        "paper_validation_runs",
        type_="foreignkey",
    )
    op.drop_column("paper_validation_runs", "last_scan_result")
    op.drop_column("paper_validation_runs", "last_tick_at")
    op.drop_column("paper_validation_runs", "last_scan_at")
    op.drop_column("paper_validation_runs", "blockers")
    op.drop_column("paper_validation_runs", "config")
    op.drop_column("paper_validation_runs", "runtime_mode")
    op.drop_column("paper_validation_runs", "strategy_version_id")
