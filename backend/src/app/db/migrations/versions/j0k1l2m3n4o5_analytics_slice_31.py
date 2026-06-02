"""Slice 31 — setup linkage on positions and paper orders for analytics."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "j0k1l2m3n4o5"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "strategy_id",
            sa.Enum(
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
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "positions",
        sa.Column(
            "strategy_id",
            sa.Enum(
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
            ),
            nullable=True,
        ),
    )
    op.add_column("positions", sa.Column("linked_proposal_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_positions_linked_proposal_id_trade_proposals"),
        "positions",
        "trade_proposals",
        ["linked_proposal_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_positions_linked_proposal_id_trade_proposals"),
        "positions",
        type_="foreignkey",
    )
    op.drop_column("positions", "linked_proposal_id")
    op.drop_column("positions", "strategy_id")
    op.drop_column("orders", "strategy_id")
