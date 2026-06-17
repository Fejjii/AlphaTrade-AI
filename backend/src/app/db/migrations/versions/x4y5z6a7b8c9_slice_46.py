"""Slice 46 — user notification preferences for alert delivery."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "x4y5z6a7b8c9"
down_revision = "w3x4y5z6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_notification_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("webhook_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("telegram_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("min_severity", sa.String(length=32), nullable=False, server_default="info"),
        sa.Column("enabled_alert_types", sa.JSON(), nullable=True),
        sa.Column(
            "quiet_hours_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("quiet_hours_start", sa.String(length=5), nullable=True),
        sa.Column("quiet_hours_end", sa.String(length=5), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("digest_mode", sa.String(length=32), nullable=False, server_default="immediate"),
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_user_notification_preferences_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_notification_preferences_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_notification_preferences")),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_user_notification_preferences_org_user",
        ),
    )


def downgrade() -> None:
    op.drop_table("user_notification_preferences")
