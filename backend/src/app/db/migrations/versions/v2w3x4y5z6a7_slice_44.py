"""Slice 44 — daily risk state optional target and trade cap."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v2w3x4y5z6a7"
down_revision = "u1v2w3x4y5z6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_risk_states",
        sa.Column("daily_target", sa.Numeric(precision=20, scale=8), nullable=True),
    )
    op.add_column(
        "daily_risk_states",
        sa.Column("max_trades_per_day", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("daily_risk_states", "max_trades_per_day")
    op.drop_column("daily_risk_states", "daily_target")
