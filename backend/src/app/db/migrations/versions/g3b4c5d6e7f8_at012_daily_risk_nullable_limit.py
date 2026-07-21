"""AT-012: allow nullable daily_loss_limit on daily_risk_states.

Revision ID: g3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-07-21

Enables create-or-update of DailyRiskState for trade_count / realized PnL
tracking even when the user has not configured an absolute daily loss limit.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "daily_risk_states",
        "daily_loss_limit",
        existing_type=sa.Numeric(precision=20, scale=8),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE daily_risk_states SET daily_loss_limit = 0 WHERE daily_loss_limit IS NULL"
        )
    )
    op.alter_column(
        "daily_risk_states",
        "daily_loss_limit",
        existing_type=sa.Numeric(precision=20, scale=8),
        nullable=False,
    )
