"""AT-038 — Automated paper-signal orchestration decisions.

Creates paper_signal_orchestration_decisions. Paper-only; no execution-path change.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p2e3f4a5b6c7"
down_revision = "o1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_signal_orchestration_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tradingview_signal_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=True),
        sa.Column("reason_summary", sa.Text(), nullable=True),
        sa.Column("eligibility_evidence", sa.JSON(), nullable=False),
        sa.Column("risk_evidence", sa.JSON(), nullable=False),
        sa.Column("transitions", sa.JSON(), nullable=False),
        sa.Column("setup_definition_id", sa.Uuid(), nullable=True),
        sa.Column("strategy_id", sa.Uuid(), nullable=True),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=True),
        sa.Column("journal_trade_id", sa.Uuid(), nullable=True),
        sa.Column("backtest_run_id", sa.Uuid(), nullable=True),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("run_plan_id", sa.Uuid(), nullable=True),
        sa.Column("proposal_id", sa.Uuid(), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["tradingview_signal_id"], ["tradingview_signals.id"]),
        sa.ForeignKeyConstraint(["setup_definition_id"], ["setup_definitions.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["user_strategies.id"]),
        sa.ForeignKeyConstraint(["strategy_version_id"], ["user_strategy_versions.id"]),
        sa.ForeignKeyConstraint(["journal_trade_id"], ["journal_trades.id"]),
        sa.ForeignKeyConstraint(["backtest_run_id"], ["backtest_runs.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["paper_validation_candidates.id"]),
        sa.ForeignKeyConstraint(["run_plan_id"], ["paper_validation_run_plans.id"]),
        sa.ForeignKeyConstraint(["proposal_id"], ["trade_proposals.id"]),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "tradingview_signal_id",
            name="uq_pso_org_signal",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_pso_org_idempotency",
        ),
    )
    op.create_index(
        "ix_paper_signal_orchestration_decisions_organization_id",
        "paper_signal_orchestration_decisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_paper_signal_orchestration_decisions_tradingview_signal_id",
        "paper_signal_orchestration_decisions",
        ["tradingview_signal_id"],
        unique=False,
    )
    op.create_index(
        "ix_pso_org_status_updated",
        "paper_signal_orchestration_decisions",
        ["organization_id", "status", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pso_org_status_updated",
        table_name="paper_signal_orchestration_decisions",
    )
    op.drop_index(
        "ix_paper_signal_orchestration_decisions_tradingview_signal_id",
        table_name="paper_signal_orchestration_decisions",
    )
    op.drop_index(
        "ix_paper_signal_orchestration_decisions_organization_id",
        table_name="paper_signal_orchestration_decisions",
    )
    op.drop_table("paper_signal_orchestration_decisions")
