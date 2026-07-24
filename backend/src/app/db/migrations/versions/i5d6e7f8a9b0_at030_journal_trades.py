"""AT-030 — canonical journal trades (journal intelligence foundation)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "i5d6e7f8a9b0"
down_revision = "h4c5d6e7f8a9"
branch_labels = None
depends_on = None

_MONEY = sa.Numeric(precision=20, scale=8)

_SOURCE_ENUM = sa.Enum(
    "MANUAL",
    "PAPER_EXECUTION",
    "PAPER_VALIDATION",
    "BACKTEST",
    "IMPORTED",
    "SYSTEM",
    name="journaltradesource",
    native_enum=False,
    length=40,
)
_STATUS_ENUM = sa.Enum(
    "PLANNED",
    "OPEN",
    "CLOSED",
    "CANCELLED",
    name="journaltradestatus",
    native_enum=False,
    length=40,
)
_REGIME_ENUM = sa.Enum(
    "TRENDING_UP",
    "TRENDING_DOWN",
    "RANGING",
    "VOLATILE",
    "QUIET",
    "UNKNOWN",
    name="marketregime",
    native_enum=False,
    length=40,
)
_DIRECTION_ENUM = sa.Enum("LONG", "SHORT", name="tradedirection", native_enum=False, length=40)
_RESULT_ENUM = sa.Enum(
    "WIN", "LOSS", "BREAKEVEN", "OPEN", name="traderesult", native_enum=False, length=40
)
_EVIDENCE_KIND_ENUM = sa.Enum(
    "SCREENSHOT",
    "CHART",
    "NOTE",
    "LINK",
    "FILE",
    name="journalevidencekind",
    native_enum=False,
    length=40,
)
_RULE_STATUS_ENUM = sa.Enum(
    "FOLLOWED",
    "VIOLATED",
    "PARTIAL",
    "NOT_APPLICABLE",
    "UNASSESSED",
    name="rulecompliancestatus",
    native_enum=False,
    length=40,
)
_OBSERVATION_CATEGORY_ENUM = sa.Enum(
    "BEHAVIORAL",
    "EMOTIONAL",
    "EXECUTION",
    "MARKET",
    "RISK",
    "PROCESS",
    name="journalobservationcategory",
    native_enum=False,
    length=40,
)


def upgrade() -> None:
    op.create_table(
        "journal_trades",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source", _SOURCE_ENUM, nullable=False),
        sa.Column("status", _STATUS_ENUM, nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("exchange", sa.String(length=40), nullable=True),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("market_regime", _REGIME_ENUM, nullable=False),
        sa.Column("regime_notes", sa.Text(), nullable=True),
        sa.Column("setup_id", sa.Uuid(), nullable=True),
        sa.Column("user_strategy_id", sa.Uuid(), nullable=True),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=True),
        sa.Column("strategy_label", sa.String(length=120), nullable=True),
        sa.Column("direction", _DIRECTION_ENUM, nullable=False),
        sa.Column("thesis", sa.Text(), nullable=True),
        sa.Column("trigger", sa.Text(), nullable=True),
        sa.Column("entry_plan", sa.Text(), nullable=True),
        sa.Column("invalidation", sa.Text(), nullable=True),
        sa.Column("planned_entry_price", _MONEY, nullable=True),
        sa.Column("planned_stop_price", _MONEY, nullable=True),
        sa.Column("planned_targets", sa.JSON(), nullable=False),
        sa.Column("runner_enabled", sa.Boolean(), nullable=False),
        sa.Column("runner_plan", sa.Text(), nullable=True),
        sa.Column("planned_risk_amount", _MONEY, nullable=True),
        sa.Column("entry_price", _MONEY, nullable=True),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", _MONEY, nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_reason", sa.String(length=60), nullable=True),
        sa.Column("size", _MONEY, nullable=True),
        sa.Column("leverage", _MONEY, nullable=True),
        sa.Column("fees", _MONEY, nullable=True),
        sa.Column("funding", _MONEY, nullable=True),
        sa.Column("slippage", _MONEY, nullable=True),
        sa.Column("gross_pnl", _MONEY, nullable=True),
        sa.Column("net_pnl", _MONEY, nullable=True),
        sa.Column("result", _RESULT_ENUM, nullable=False),
        sa.Column("mfe_price", _MONEY, nullable=True),
        sa.Column("mae_price", _MONEY, nullable=True),
        sa.Column("mfe_amount", _MONEY, nullable=True),
        sa.Column("mae_amount", _MONEY, nullable=True),
        sa.Column("available_profit", _MONEY, nullable=True),
        sa.Column("realized_vs_available_pct", sa.Float(), nullable=True),
        sa.Column("excursion_source", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("linked_position_id", sa.Uuid(), nullable=True),
        sa.Column("linked_paper_trade_id", sa.Uuid(), nullable=True),
        sa.Column("linked_proposal_id", sa.Uuid(), nullable=True),
        sa.Column("linked_order_id", sa.Uuid(), nullable=True),
        sa.Column("linked_backtest_trade_id", sa.Uuid(), nullable=True),
        sa.Column("linked_journal_entry_id", sa.Uuid(), nullable=True),
        sa.Column("linked_paper_validation_run_id", sa.Uuid(), nullable=True),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["setup_id"], ["setup_definitions.id"]),
        sa.ForeignKeyConstraint(["user_strategy_id"], ["user_strategies.id"]),
        sa.ForeignKeyConstraint(["strategy_version_id"], ["user_strategy_versions.id"]),
        sa.ForeignKeyConstraint(["linked_position_id"], ["positions.id"]),
        sa.ForeignKeyConstraint(["linked_paper_trade_id"], ["paper_trades.id"]),
        sa.ForeignKeyConstraint(["linked_proposal_id"], ["trade_proposals.id"]),
        sa.ForeignKeyConstraint(["linked_order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["linked_backtest_trade_id"], ["backtest_trades.id"]),
        sa.ForeignKeyConstraint(["linked_journal_entry_id"], ["journals.id"]),
        sa.ForeignKeyConstraint(["linked_paper_validation_run_id"], ["paper_validation_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_journal_trades_organization_id"), "journal_trades", ["organization_id"]
    )
    op.create_index(op.f("ix_journal_trades_user_id"), "journal_trades", ["user_id"])
    op.create_index(op.f("ix_journal_trades_symbol"), "journal_trades", ["symbol"])
    op.create_index(
        "ix_journal_trades_org_user_created",
        "journal_trades",
        ["organization_id", "user_id", "created_at"],
    )

    op.create_table(
        "journal_trade_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("journal_trade_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("kind", _EVIDENCE_KIND_ENUM, nullable=False),
        sa.Column("ref", sa.String(length=1024), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["journal_trade_id"], ["journal_trades.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_journal_trade_evidence_journal_trade_id"),
        "journal_trade_evidence",
        ["journal_trade_id"],
    )
    op.create_index(
        op.f("ix_journal_trade_evidence_organization_id"),
        "journal_trade_evidence",
        ["organization_id"],
    )

    op.create_table(
        "journal_trade_rule_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("journal_trade_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("rule_key", sa.String(length=120), nullable=False),
        sa.Column("rule_source", sa.String(length=40), nullable=True),
        sa.Column("status", _RULE_STATUS_ENUM, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("assessed_by", sa.Uuid(), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["journal_trade_id"], ["journal_trades.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["assessed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_journal_trade_rule_checks_journal_trade_id"),
        "journal_trade_rule_checks",
        ["journal_trade_id"],
    )
    op.create_index(
        op.f("ix_journal_trade_rule_checks_organization_id"),
        "journal_trade_rule_checks",
        ["organization_id"],
    )

    op.create_table(
        "journal_trade_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("journal_trade_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("category", _OBSERVATION_CATEGORY_ENUM, nullable=False),
        sa.Column("observation", sa.Text(), nullable=False),
        sa.Column("emotion_tags", sa.JSON(), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["journal_trade_id"], ["journal_trades.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_journal_trade_observations_journal_trade_id"),
        "journal_trade_observations",
        ["journal_trade_id"],
    )
    op.create_index(
        op.f("ix_journal_trade_observations_organization_id"),
        "journal_trade_observations",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_journal_trade_observations_organization_id"),
        table_name="journal_trade_observations",
    )
    op.drop_index(
        op.f("ix_journal_trade_observations_journal_trade_id"),
        table_name="journal_trade_observations",
    )
    op.drop_table("journal_trade_observations")
    op.drop_index(
        op.f("ix_journal_trade_rule_checks_organization_id"),
        table_name="journal_trade_rule_checks",
    )
    op.drop_index(
        op.f("ix_journal_trade_rule_checks_journal_trade_id"),
        table_name="journal_trade_rule_checks",
    )
    op.drop_table("journal_trade_rule_checks")
    op.drop_index(
        op.f("ix_journal_trade_evidence_organization_id"), table_name="journal_trade_evidence"
    )
    op.drop_index(
        op.f("ix_journal_trade_evidence_journal_trade_id"), table_name="journal_trade_evidence"
    )
    op.drop_table("journal_trade_evidence")
    op.drop_index("ix_journal_trades_org_user_created", table_name="journal_trades")
    op.drop_index(op.f("ix_journal_trades_symbol"), table_name="journal_trades")
    op.drop_index(op.f("ix_journal_trades_user_id"), table_name="journal_trades")
    op.drop_index(op.f("ix_journal_trades_organization_id"), table_name="journal_trades")
    op.drop_table("journal_trades")
