"""AT-034 — backtest domain v2 (datasets, run metadata, trade excursions).

Adds:
- global immutable ``backtest_datasets`` table (candle-window snapshots);
- nullable AT-034 columns on ``backtest_runs`` (config/dataset/engine hashes,
  idempotency, progress, bar counters) with partial unique index on
  (organization_id, idempotency_key);
- nullable excursion / funding / split columns on ``backtest_trades``.

Paper-only; no execution-path change. Supports upgrade AND downgrade.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "m9b0c1d2e3f4"
down_revision = "l8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("exchange", sa.String(length=40), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("candle_count", sa.Integer(), nullable=False),
        sa.Column("first_open_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_open_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gap_count", sa.Integer(), nullable=False),
        sa.Column("source_counts", sa.JSON(), nullable=False),
        sa.Column("stale_count", sa.Integer(), nullable=False),
        sa.Column("dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_hash", name="uq_backtest_datasets_dataset_hash"),
    )

    op.add_column("backtest_runs", sa.Column("config_snapshot", sa.JSON(), nullable=True))
    op.add_column("backtest_runs", sa.Column("config_hash", sa.String(length=64), nullable=True))
    op.add_column("backtest_runs", sa.Column("dataset_id", sa.Uuid(), nullable=True))
    op.add_column("backtest_runs", sa.Column("engine_version", sa.String(length=40), nullable=True))
    op.add_column("backtest_runs", sa.Column("result_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "backtest_runs", sa.Column("idempotency_key", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "backtest_runs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "backtest_runs", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "backtest_runs",
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("backtest_runs", sa.Column("processed_bars", sa.Integer(), nullable=True))
    op.add_column("backtest_runs", sa.Column("total_bars", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_backtest_runs_dataset_id_backtest_datasets",
        "backtest_runs",
        "backtest_datasets",
        ["dataset_id"],
        ["id"],
    )
    op.create_index(
        "uq_backtest_runs_org_idempotency_key",
        "backtest_runs",
        ["organization_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.add_column(
        "backtest_trades", sa.Column("mfe_price", sa.Numeric(precision=20, scale=8), nullable=True)
    )
    op.add_column(
        "backtest_trades", sa.Column("mae_price", sa.Numeric(precision=20, scale=8), nullable=True)
    )
    op.add_column(
        "backtest_trades", sa.Column("mfe_amount", sa.Numeric(precision=20, scale=8), nullable=True)
    )
    op.add_column(
        "backtest_trades", sa.Column("mae_amount", sa.Numeric(precision=20, scale=8), nullable=True)
    )
    op.add_column(
        "backtest_trades",
        sa.Column("available_profit", sa.Numeric(precision=20, scale=8), nullable=True),
    )
    op.add_column(
        "backtest_trades",
        sa.Column("capture_pct", sa.Numeric(precision=20, scale=8), nullable=True),
    )
    op.add_column(
        "backtest_trades",
        sa.Column("funding_cost", sa.Numeric(precision=20, scale=8), nullable=True),
    )
    op.add_column("backtest_trades", sa.Column("split_label", sa.String(length=20), nullable=True))
    op.add_column("backtest_trades", sa.Column("split_index", sa.Integer(), nullable=True))
    op.add_column("backtest_trades", sa.Column("sequence", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("backtest_trades", "sequence")
    op.drop_column("backtest_trades", "split_index")
    op.drop_column("backtest_trades", "split_label")
    op.drop_column("backtest_trades", "funding_cost")
    op.drop_column("backtest_trades", "capture_pct")
    op.drop_column("backtest_trades", "available_profit")
    op.drop_column("backtest_trades", "mae_amount")
    op.drop_column("backtest_trades", "mfe_amount")
    op.drop_column("backtest_trades", "mae_price")
    op.drop_column("backtest_trades", "mfe_price")

    op.drop_index("uq_backtest_runs_org_idempotency_key", table_name="backtest_runs")
    op.drop_constraint(
        "fk_backtest_runs_dataset_id_backtest_datasets",
        "backtest_runs",
        type_="foreignkey",
    )
    op.drop_column("backtest_runs", "total_bars")
    op.drop_column("backtest_runs", "processed_bars")
    op.drop_column("backtest_runs", "cancel_requested_at")
    op.drop_column("backtest_runs", "finished_at")
    op.drop_column("backtest_runs", "started_at")
    op.drop_column("backtest_runs", "idempotency_key")
    op.drop_column("backtest_runs", "result_hash")
    op.drop_column("backtest_runs", "engine_version")
    op.drop_column("backtest_runs", "dataset_id")
    op.drop_column("backtest_runs", "config_hash")
    op.drop_column("backtest_runs", "config_snapshot")

    op.drop_table("backtest_datasets")
