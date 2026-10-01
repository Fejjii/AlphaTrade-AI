"""Persist existing canonical public-market observation envelopes.

Revision ID: a2sfp002
Revises: a1brain001
"""
import sqlalchemy as sa
from alembic import op

revision = "a2sfp002"
down_revision = "a1brain001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "public_market_observations",
        sa.Column("identity_hash", sa.String(64), primary_key=True),
        sa.Column("observation_id", sa.Uuid(), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("bar_start", sa.DateTime(timezone=True)),
        sa.Column("ohlcv", sa.JSON()),
    )
    op.create_index(
        "ix_public_observation_identity_time", "public_market_observations",
        ["identity_hash", "bar_start"],
    )


def downgrade():
    op.drop_index("ix_public_observation_identity_time", table_name="public_market_observations")
    op.drop_table("public_market_observations")
