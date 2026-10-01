"""Organization Watcher configuration and latest runtime observations.

Revision ID: b6f2d9a10e73
Revises: a8c3e1b94d20
"""

import sqlalchemy as sa
from alembic import op

revision = "b6f2d9a10e73"
down_revision = "a8c3e1b94d20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watcher_watchlists",
        sa.Column(
            "organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), primary_key=True
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("slots", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("runtime_summary", sa.JSON(), nullable=True),
        sa.CheckConstraint("revision >= 0", name="watchlist_revision"),
    )
    op.create_table(
        "watcher_symbol_status",
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("watcher_watchlists.organization_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("symbol", sa.String(20), primary_key=True),
        sa.Column("configuration_revision", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("watcher_symbol_status")
    op.drop_table("watcher_watchlists")
