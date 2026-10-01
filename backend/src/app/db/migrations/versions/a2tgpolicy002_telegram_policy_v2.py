"""Versioned Telegram policies on existing preference and outbox records."""

import sqlalchemy as sa
from alembic import op

revision = "a2tgpolicy002"
down_revision = "a1brain001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "telegram_security_outbox", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "user_notification_preferences", sa.Column("telegram_policy", sa.JSON(), nullable=True)
    )
    op.add_column(
        "telegram_security_outbox", sa.Column("notification_event", sa.JSON(), nullable=True)
    )
    op.create_index(
        "ix_tgsec_outbox_policy_history",
        "telegram_security_outbox",
        ["organization_id", "user_id", "bot_id", "chat_id", "created_at"],
    )


def downgrade():
    # Older code cannot parse SUPPRESSED. Preserve its terminal, non-deliverable state.
    op.execute(
        "UPDATE telegram_security_outbox SET state = 'DEAD_LETTER' WHERE state = 'SUPPRESSED'"
    )
    op.drop_index("ix_tgsec_outbox_policy_history", table_name="telegram_security_outbox")
    op.drop_column("telegram_security_outbox", "notification_event")
    op.drop_column("telegram_security_outbox", "sent_at")
    op.drop_column("user_notification_preferences", "telegram_policy")
