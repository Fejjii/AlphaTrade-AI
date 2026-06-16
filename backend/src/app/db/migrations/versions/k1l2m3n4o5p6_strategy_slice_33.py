"""Slice 33 — strategy library, manual levels, loss acceptance."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "k1l2m3n4o5p6"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None

_STRATEGY_ID_ENUM = sa.Enum(
    "HTF_TREND_PULLBACK",
    "LIQUIDITY_SWEEP_REVERSAL",
    "COUNTERTREND_SHORT_BUILD",
    "PASSIVE_LEVEL_ORDER",
    "PROFIT_PROTECTION",
    "GREEN_DAY_GUARD",
    "MENTAL_CAPITAL_GUARD",
    "MANUAL_REVIEW",
    name="strategyid",
    native_enum=False,
    length=40,
)


def upgrade() -> None:
    op.create_table(
        "user_strategies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("setup_type", _STRATEGY_ID_ENUM, nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            "name",
            name="uq_user_strategy_org_user_name",
        ),
    )
    op.create_table(
        "user_strategy_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("card", sa.JSON(), nullable=False),
        sa.Column(
            "validation_status",
            sa.Enum(
                "DRAFT",
                "IN_REVIEW",
                "VALIDATED",
                "NEEDS_REVISION",
                "DEPRECATED",
                name="strategyvalidationstatus",
                native_enum=False,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column(
            "backtest_status",
            sa.Enum(
                "NOT_RUN",
                "SCHEDULED",
                "RUNNING",
                "COMPLETE",
                "FAILED",
                name="backteststatus",
                native_enum=False,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column(
            "paper_validation_status",
            sa.Enum(
                "NOT_STARTED",
                "IN_PROGRESS",
                "PASSED",
                "FAILED",
                name="papervalidationstatus",
                native_enum=False,
                length=40,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["strategy_id"], ["user_strategies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy_id", "version", name="uq_user_strategy_version"),
    )
    op.create_table(
        "manual_chart_levels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("exchange", sa.String(length=40), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=True),
        sa.Column(
            "level_type",
            sa.Enum(
                "SUPPORT",
                "RESISTANCE",
                "FIBONACCI",
                "TREND_LINE",
                "VWAP",
                "LIQUIDITY_ZONE",
                "PREVIOUS_HIGH",
                "PREVIOUS_LOW",
                "USER_NOTE",
                name="manualleveltype",
                native_enum=False,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("price_low", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("price_high", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "trade_proposals",
        sa.Column("user_strategy_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "trade_proposals",
        sa.Column("planned_loss_amount", sa.Numeric(precision=20, scale=8), nullable=True),
    )
    op.add_column(
        "trade_proposals",
        sa.Column("loss_acceptance_required", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "trade_proposals",
        sa.Column(
            "loss_acceptance_status",
            sa.Enum(
                "NOT_REQUIRED",
                "PENDING",
                "ACCEPTED",
                "REJECTED",
                name="lossacceptancestatus",
                native_enum=False,
                length=40,
            ),
            nullable=False,
            server_default="NOT_REQUIRED",
        ),
    )
    op.add_column(
        "trade_proposals",
        sa.Column("actual_loss_amount", sa.Numeric(precision=20, scale=8), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_trade_proposals_user_strategy_id_user_strategies"),
        "trade_proposals",
        "user_strategies",
        ["user_strategy_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_trade_proposals_user_strategy_id_user_strategies"),
        "trade_proposals",
        type_="foreignkey",
    )
    op.drop_column("trade_proposals", "actual_loss_amount")
    op.drop_column("trade_proposals", "loss_acceptance_status")
    op.drop_column("trade_proposals", "loss_acceptance_required")
    op.drop_column("trade_proposals", "planned_loss_amount")
    op.drop_column("trade_proposals", "user_strategy_id")
    op.drop_table("manual_chart_levels")
    op.drop_table("user_strategy_versions")
    op.drop_table("user_strategies")
