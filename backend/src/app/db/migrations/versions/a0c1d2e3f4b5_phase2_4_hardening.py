"""phase 2-4 hardening: pattern spec, hash backfill, journal identity, levels

Revision ID: a0c1d2e3f4b5
Revises: 9b0c1d2e3f4a
Create Date: 2026-09-16 12:40:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.strategy_immutability import (
    backfill_strategy_version_content_hashes,
    strategy_version_pg_immutability_install_statements,
    strategy_version_pg_immutability_uninstall_statements,
)

revision: str = "a0c1d2e3f4b5"
down_revision: str | None = "9b0c1d2e3f4a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _rebuild_source_unique(table: str, include_account: bool) -> None:
    constraint = (
        "uq_journal_lifecycle_event_source"
        if table == "journal_lifecycle_events"
        else "uq_journal_projection_receipt_source"
    )
    cols = [
        "organization_id",
        "account_id",
        "source_system",
        "source_aggregate",
        "event_type",
        "source_event_id",
        "source_event_version",
        "supersession",
    ]
    if not include_account:
        cols = [column for column in cols if column != "account_id"]
    if _is_postgres():
        op.drop_constraint(constraint, table, type_="unique")
        op.create_unique_constraint(constraint, table, cols)
        return
    with op.batch_alter_table(table) as batch:
        batch.drop_constraint(constraint, type_="unique")
        batch.create_unique_constraint(constraint, cols)


def upgrade() -> None:
    op.add_column("user_strategy_versions", sa.Column("pattern_spec", sa.JSON(), nullable=True))
    op.add_column(
        "journal_trades",
        sa.Column("projector_watermark_rank", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "journal_trades",
        sa.Column("projector_lock_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "manual_level_revisions",
        sa.Column("venue", sa.String(length=40), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "manual_level_revisions",
        sa.Column("market_type", sa.String(length=40), nullable=False, server_default="unspecified"),
    )
    op.add_column(
        "manual_level_revisions",
        sa.Column("price_unit", sa.String(length=20), nullable=False, server_default="quote"),
    )

    bind = op.get_bind()
    bind.execute(sa.text("UPDATE manual_level_revisions SET venue = exchange"))

    op.alter_column(
        "journal_lifecycle_events",
        "account_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.alter_column(
        "journal_projection_receipts",
        "account_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    _rebuild_source_unique("journal_lifecycle_events", include_account=True)
    _rebuild_source_unique("journal_projection_receipts", include_account=True)

    backfill_strategy_version_content_hashes(bind)
    if _is_postgres():
        op.execute("ALTER TABLE user_strategy_versions ALTER COLUMN content_hash SET NOT NULL")
        op.execute(
            "ALTER TABLE user_strategy_versions "
            "ADD CONSTRAINT ck_user_strategy_version_hash CHECK (length(content_hash) = 64)"
        )
        for statement in strategy_version_pg_immutability_install_statements():
            op.execute(statement)
        return
    with op.batch_alter_table("user_strategy_versions") as batch:
        batch.alter_column("content_hash", existing_type=sa.String(length=64), nullable=False)
        batch.create_check_constraint("ck_user_strategy_version_hash", "length(content_hash) = 64")


def downgrade() -> None:
    bind = op.get_bind()
    if _is_postgres():
        for statement in strategy_version_pg_immutability_uninstall_statements():
            op.execute(statement)
        op.execute(
            "ALTER TABLE user_strategy_versions DROP CONSTRAINT IF EXISTS "
            "ck_user_strategy_version_hash"
        )
        op.execute("ALTER TABLE user_strategy_versions ALTER COLUMN content_hash DROP NOT NULL")
    else:
        with op.batch_alter_table("user_strategy_versions") as batch:
            batch.drop_constraint("ck_user_strategy_version_hash", type_="check")
            batch.alter_column("content_hash", existing_type=sa.String(length=64), nullable=True)

    _rebuild_source_unique("journal_projection_receipts", include_account=False)
    _rebuild_source_unique("journal_lifecycle_events", include_account=False)
    op.alter_column("journal_projection_receipts", "account_id", existing_type=sa.Uuid(), nullable=True)
    op.alter_column("journal_lifecycle_events", "account_id", existing_type=sa.Uuid(), nullable=True)

    op.drop_column("manual_level_revisions", "price_unit")
    op.drop_column("manual_level_revisions", "market_type")
    op.drop_column("manual_level_revisions", "venue")
    op.drop_column("journal_trades", "projector_lock_version")
    op.drop_column("journal_trades", "projector_watermark_rank")
    op.drop_column("user_strategy_versions", "pattern_spec")
    del bind
