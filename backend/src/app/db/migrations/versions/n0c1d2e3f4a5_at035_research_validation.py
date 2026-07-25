"""AT-035 — research validation provenance on paper validation candidates.

Adds nullable research-promotion columns and a partial unique index so an
organization can have only one active (queued/reviewing) candidate per
backtest_run_id. Paper-only; no execution-path change.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "n0c1d2e3f4a5"
down_revision = "m9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "paper_validation_candidates",
        sa.Column("promotion_source", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "paper_validation_candidates",
        sa.Column("backtest_run_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "paper_validation_candidates",
        sa.Column("strategy_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "paper_validation_candidates",
        sa.Column("strategy_version_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "paper_validation_candidates",
        sa.Column("dataset_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "paper_validation_candidates",
        sa.Column("config_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "paper_validation_candidates",
        sa.Column("result_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "paper_validation_candidates",
        sa.Column("evidence_tier", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "paper_validation_candidates",
        sa.Column("sample_size", sa.Integer(), nullable=True),
    )
    op.add_column(
        "paper_validation_candidates",
        sa.Column("oos_expectancy", sa.Numeric(20, 8), nullable=True),
    )
    op.add_column(
        "paper_validation_candidates",
        sa.Column("regime", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "paper_validation_candidates",
        sa.Column("evidence_snapshot", sa.JSON(), nullable=True),
    )
    op.create_foreign_key(
        "fk_pvc_backtest_run_id",
        "paper_validation_candidates",
        "backtest_runs",
        ["backtest_run_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_pvc_strategy_id",
        "paper_validation_candidates",
        "user_strategies",
        ["strategy_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_pvc_strategy_version_id",
        "paper_validation_candidates",
        "user_strategy_versions",
        ["strategy_version_id"],
        ["id"],
    )
    op.create_index(
        "ix_paper_validation_candidates_backtest_run_id",
        "paper_validation_candidates",
        ["backtest_run_id"],
    )
    op.create_index(
        "uq_pvc_org_backtest_active",
        "paper_validation_candidates",
        ["organization_id", "backtest_run_id"],
        unique=True,
        sqlite_where=sa.text(
            "backtest_run_id IS NOT NULL AND candidate_status IN ('queued', 'reviewing')"
        ),
        postgresql_where=sa.text(
            "backtest_run_id IS NOT NULL AND candidate_status IN ('queued', 'reviewing')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_pvc_org_backtest_active", table_name="paper_validation_candidates")
    op.drop_index(
        "ix_paper_validation_candidates_backtest_run_id",
        table_name="paper_validation_candidates",
    )
    op.drop_constraint(
        "fk_pvc_strategy_version_id",
        "paper_validation_candidates",
        type_="foreignkey",
    )
    op.drop_constraint("fk_pvc_strategy_id", "paper_validation_candidates", type_="foreignkey")
    op.drop_constraint("fk_pvc_backtest_run_id", "paper_validation_candidates", type_="foreignkey")
    op.drop_column("paper_validation_candidates", "evidence_snapshot")
    op.drop_column("paper_validation_candidates", "regime")
    op.drop_column("paper_validation_candidates", "oos_expectancy")
    op.drop_column("paper_validation_candidates", "sample_size")
    op.drop_column("paper_validation_candidates", "evidence_tier")
    op.drop_column("paper_validation_candidates", "result_hash")
    op.drop_column("paper_validation_candidates", "config_hash")
    op.drop_column("paper_validation_candidates", "dataset_hash")
    op.drop_column("paper_validation_candidates", "strategy_version_id")
    op.drop_column("paper_validation_candidates", "strategy_id")
    op.drop_column("paper_validation_candidates", "backtest_run_id")
    op.drop_column("paper_validation_candidates", "promotion_source")
