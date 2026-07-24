"""AT-031 — journal statistics supporting indexes.

Composite indexes for the bounded statistics scans over ``journal_trades``
(org + user + closed status + effective time ordering, and the id-based filter
dimensions) plus an org+status index on ``journal_trade_rule_checks`` for the
rule-compliance classification query. Index-only change; no data migration.
"""

from __future__ import annotations

from alembic import op

revision = "j6e7f8a9b0c1"
down_revision = "i5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_journal_trades_org_user_status_exit",
        "journal_trades",
        ["organization_id", "user_id", "status", "exit_time"],
    )
    op.create_index(
        "ix_journal_trades_org_setup",
        "journal_trades",
        ["organization_id", "setup_id"],
    )
    op.create_index(
        "ix_journal_trades_org_strategy",
        "journal_trades",
        ["organization_id", "user_strategy_id"],
    )
    op.create_index(
        "ix_journal_trades_org_strategy_version",
        "journal_trades",
        ["organization_id", "strategy_version_id"],
    )
    op.create_index(
        "ix_journal_trade_rule_checks_org_status",
        "journal_trade_rule_checks",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_journal_trade_rule_checks_org_status", table_name="journal_trade_rule_checks")
    op.drop_index("ix_journal_trades_org_strategy_version", table_name="journal_trades")
    op.drop_index("ix_journal_trades_org_strategy", table_name="journal_trades")
    op.drop_index("ix_journal_trades_org_setup", table_name="journal_trades")
    op.drop_index("ix_journal_trades_org_user_status_exit", table_name="journal_trades")
