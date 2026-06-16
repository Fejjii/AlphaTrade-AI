"""Slice 35 — historical candles, backtest trades, paper validation metrics."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "m3n4o5p6q7r8"
down_revision = "l2m3n4o5p6q7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historical_candles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("exchange", sa.String(length=40), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(20, 8), nullable=False),
        sa.Column("high", sa.Numeric(20, 8), nullable=False),
        sa.Column("low", sa.Numeric(20, 8), nullable=False),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("volume", sa.Numeric(20, 8), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("freshness_note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol",
            "exchange",
            "timeframe",
            "open_time",
            name="uq_historical_candle",
        ),
    )
    op.create_index(
        "ix_historical_candles_lookup",
        "historical_candles",
        ["symbol", "exchange", "timeframe", "open_time"],
    )

    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("backtest_run_id", sa.Uuid(), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("exit_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("stop_loss", sa.Numeric(20, 8), nullable=False),
        sa.Column("size", sa.Numeric(20, 8), nullable=False),
        sa.Column("fees", sa.Numeric(20, 8), nullable=False),
        sa.Column("slippage_cost", sa.Numeric(20, 8), nullable=False),
        sa.Column("gross_pnl", sa.Numeric(20, 8), nullable=False),
        sa.Column("net_pnl", sa.Numeric(20, 8), nullable=False),
        sa.Column("tp_hit_status", sa.String(length=40), nullable=False),
        sa.Column("exit_reason", sa.String(length=60), nullable=False),
        sa.Column("rule_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["backtest_run_id"], ["backtest_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column(
        "paper_validation_runs",
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "paper_validation_runs",
        sa.Column("metrics", sa.JSON(), nullable=True),
    )
    op.add_column(
        "paper_validation_runs",
        sa.Column(
            "recommendation",
            sa.String(length=40),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("paper_validation_runs", "recommendation")
    op.drop_column("paper_validation_runs", "metrics")
    op.drop_column("paper_validation_runs", "ended_at")
    op.drop_table("backtest_trades")
    op.drop_index("ix_historical_candles_lookup", table_name="historical_candles")
    op.drop_table("historical_candles")
