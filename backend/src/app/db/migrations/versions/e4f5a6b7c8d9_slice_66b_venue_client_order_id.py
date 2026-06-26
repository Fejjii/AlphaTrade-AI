"""Slice 66b — store venue-safe client order id on exchange orders."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exchange_orders",
        sa.Column("venue_client_order_id", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("exchange_orders", "venue_client_order_id")
