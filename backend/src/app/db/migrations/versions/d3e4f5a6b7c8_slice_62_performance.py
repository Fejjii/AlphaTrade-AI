"""Slice 62 — performance analytics: snapshots and per-strategy daily rollups."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "performance_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False, server_default="account"),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("net_pnl", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("gross_profit", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("gross_loss", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("total_fees", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("total_funding", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("win_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("profit_factor", sa.Float(), nullable=True),
        sa.Column("expectancy", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("avg_r_multiple", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("max_drawdown_pct", sa.Float(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_performance_snapshots_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_performance_snapshots_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_performance_snapshots")),
    )

    op.create_table(
        "strategy_performance_daily",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("strategy_id", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("net_pnl", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("win_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("profit_factor", sa.Float(), nullable=True),
        sa.Column("expectancy", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("max_drawdown", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_strategy_performance_daily_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_strategy_performance_daily")),
        sa.UniqueConstraint(
            "organization_id",
            "strategy_id",
            "day",
            name="uq_strategy_perf_daily_org_strategy_day",
        ),
    )


def downgrade() -> None:
    op.drop_table("strategy_performance_daily")
    op.drop_table("performance_snapshots")
