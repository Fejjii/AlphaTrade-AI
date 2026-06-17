"""Slice 45 — user risk settings for paper discipline."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "w3x4y5z6a7b8"
down_revision = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_risk_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("daily_loss_limit", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("daily_target", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("max_trades_per_day", sa.Integer(), nullable=False, server_default="20"),
        sa.Column(
            "max_risk_per_trade_percent",
            sa.Numeric(precision=20, scale=8),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "default_account_balance",
            sa.Numeric(precision=20, scale=8),
            nullable=False,
            server_default="10000",
        ),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column(
            "green_day_protection_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "one_loss_stop_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "overtrading_guard_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_user_risk_settings_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_risk_settings_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_risk_settings")),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_user_risk_settings_org_user",
        ),
    )


def downgrade() -> None:
    op.drop_table("user_risk_settings")
