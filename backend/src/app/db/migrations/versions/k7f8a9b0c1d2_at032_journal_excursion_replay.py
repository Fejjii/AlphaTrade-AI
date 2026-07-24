"""AT-032 — journal trade excursion replay provenance columns.

Adds data-source / freshness provenance for deterministic HistoricalCandle
replay of MFE/MAE and available-vs-realized metrics. No execution-path change.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "k7f8a9b0c1d2"
down_revision = "j6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "journal_trades",
        sa.Column("excursion_data_source", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "journal_trades",
        sa.Column("excursion_is_stale", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "journal_trades",
        sa.Column("excursion_freshness_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "journal_trades",
        sa.Column("excursion_candle_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "journal_trades",
        sa.Column("excursion_gaps_detected", sa.Integer(), nullable=True),
    )
    op.add_column(
        "journal_trades",
        sa.Column("excursion_window_complete", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "journal_trades",
        sa.Column(
            "excursion_computed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_journal_trades_org_user_excursion_source",
        "journal_trades",
        ["organization_id", "user_id", "excursion_source"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_journal_trades_org_user_excursion_source",
        table_name="journal_trades",
    )
    op.drop_column("journal_trades", "excursion_computed_at")
    op.drop_column("journal_trades", "excursion_window_complete")
    op.drop_column("journal_trades", "excursion_gaps_detected")
    op.drop_column("journal_trades", "excursion_candle_count")
    op.drop_column("journal_trades", "excursion_freshness_note")
    op.drop_column("journal_trades", "excursion_is_stale")
    op.drop_column("journal_trades", "excursion_data_source")
