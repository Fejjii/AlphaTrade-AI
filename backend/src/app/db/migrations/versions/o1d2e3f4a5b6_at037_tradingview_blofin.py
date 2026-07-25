"""AT-037 — TradingView signal intake + BloFin demo read-only sync.

Creates tradingview_signals and blofin_demo_sync_snapshots. Paper/demo only;
no execution-path change.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "o1d2e3f4a5b6"
down_revision = "n0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tradingview_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("external_alert_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("setup_name", sa.String(length=120), nullable=True),
        sa.Column("setup_version", sa.Integer(), nullable=True),
        sa.Column("setup_definition_id", sa.Uuid(), nullable=True),
        sa.Column("strategy_id", sa.Uuid(), nullable=True),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=True),
        sa.Column("trigger_level", sa.Float(), nullable=True),
        sa.Column("invalidation_level", sa.Float(), nullable=True),
        sa.Column("take_profit_level", sa.Float(), nullable=True),
        sa.Column("stop_loss_level", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_metadata", sa.JSON(), nullable=True),
        sa.Column("raw_payload_redacted", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duplicate_of_signal_id", sa.Uuid(), nullable=True),
        sa.Column("source_alert_id", sa.Uuid(), nullable=True),
        sa.Column("draft_id", sa.Uuid(), nullable=True),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("journal_trade_id", sa.Uuid(), nullable=True),
        sa.Column("backtest_run_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["setup_definition_id"], ["setup_definitions.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["user_strategies.id"]),
        sa.ForeignKeyConstraint(["strategy_version_id"], ["user_strategy_versions.id"]),
        sa.ForeignKeyConstraint(["duplicate_of_signal_id"], ["tradingview_signals.id"]),
        sa.ForeignKeyConstraint(["source_alert_id"], ["paper_validation_alerts.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["paper_validation_drafts.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["paper_validation_candidates.id"]),
        sa.ForeignKeyConstraint(["journal_trade_id"], ["journal_trades.id"]),
        sa.ForeignKeyConstraint(["backtest_run_id"], ["backtest_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_tv_signal_org_idempotency",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "external_alert_id",
            name="uq_tv_signal_org_alert",
        ),
    )
    op.create_index(
        "ix_tradingview_signals_organization_id",
        "tradingview_signals",
        ["organization_id"],
    )
    op.create_index(
        "ix_tv_signals_org_status_received",
        "tradingview_signals",
        ["organization_id", "status", "received_at"],
    )

    op.create_table(
        "blofin_demo_sync_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("health_status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("exchange_mode", sa.String(length=40), nullable=False),
        sa.Column("account_snapshot", sa.JSON(), nullable=False),
        sa.Column("positions_snapshot", sa.JSON(), nullable=False),
        sa.Column("market_context", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False),
        sa.Column("stale_reason", sa.Text(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("position_count", sa.Integer(), nullable=False),
        sa.Column("balance_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_blofin_demo_sync_snapshots_organization_id",
        "blofin_demo_sync_snapshots",
        ["organization_id"],
    )
    op.create_index(
        "ix_blofin_sync_org_synced_at",
        "blofin_demo_sync_snapshots",
        ["organization_id", "synced_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_blofin_sync_org_synced_at", table_name="blofin_demo_sync_snapshots")
    op.drop_index(
        "ix_blofin_demo_sync_snapshots_organization_id",
        table_name="blofin_demo_sync_snapshots",
    )
    op.drop_table("blofin_demo_sync_snapshots")
    op.drop_index("ix_tv_signals_org_status_received", table_name="tradingview_signals")
    op.drop_index("ix_tradingview_signals_organization_id", table_name="tradingview_signals")
    op.drop_table("tradingview_signals")
