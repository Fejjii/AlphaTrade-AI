"""phase 8 learning attribution postgres persistence

Revision ID: d4f7a2c8e901
Revises: c9e2b4a1d078
Create Date: 2026-09-19 12:50:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.historical_immutability import historical_immutability_phase8_install_statements

revision: str = "d4f7a2c8e901"
down_revision: str | None = "c9e2b4a1d078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IDENTITY_FUNCTION = "alphatrade_forbid_learning_attribution_identity_mutation"
_IDENTITY_TRIGGER = "trg_learning_attribution_records_identity_immutable"
_EVENT_TRIGGER = "trg_learning_attribution_events_immutable"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.add_column("journal_trades", sa.Column("candidate_id", sa.Uuid(), nullable=True))
    op.add_column("journal_trades", sa.Column("assessment_id", sa.Uuid(), nullable=True))
    op.add_column(
        "journal_trades",
        sa.Column("evidence_window_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "journal_trades",
        sa.Column("trade_plan_revision_id", sa.Uuid(), nullable=True),
    )
    op.create_check_constraint(
        "ck_journal_trades_lineage_window_hash",
        "journal_trades",
        "evidence_window_hash IS NULL OR length(evidence_window_hash) = 64",
    )
    op.create_index(
        "ix_journal_trades_org_candidate",
        "journal_trades",
        ["organization_id", "candidate_id"],
    )

    op.create_table(
        "learning_attribution_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_window_hash", sa.String(length=64), nullable=False),
        sa.Column("uniqueness_tuple_hash", sa.String(length=64), nullable=False),
        sa.Column("candidate_content_hash", sa.String(length=64), nullable=False),
        sa.Column("execution_lifecycle_id", sa.Uuid(), nullable=True),
        sa.Column("journal_trade_id", sa.Uuid(), nullable=True),
        sa.Column("trade_plan_revision_id", sa.Uuid(), nullable=True),
        sa.Column("facts_hash", sa.String(length=64), nullable=False),
        sa.Column("executed_trade_outcome", sa.Boolean(), nullable=False),
        sa.Column("learning_venue_mode", sa.String(length=32), nullable=False),
        sa.Column("setup_quality_axis", sa.String(length=32), nullable=False),
        sa.Column("execution_quality_axis", sa.String(length=32), nullable=False),
        sa.Column("risk_adherence_axis", sa.String(length=32), nullable=False),
        sa.Column("trader_behavior_axis", sa.String(length=32), nullable=False),
        sa.Column("decision_actor", sa.String(length=32), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=False),
        sa.Column("setup_definition_id", sa.Uuid(), nullable=False),
        sa.Column("fusion_policy_version", sa.String(length=120), nullable=False),
        sa.Column("rejected", sa.Boolean(), nullable=False),
        sa.Column("skipped", sa.Boolean(), nullable=False),
        sa.Column("plan_approved", sa.Boolean(), nullable=False),
        sa.Column("filled", sa.Boolean(), nullable=False),
        sa.Column("closed", sa.Boolean(), nullable=False),
        sa.Column("win", sa.Boolean(), nullable=False),
        sa.Column("loss", sa.Boolean(), nullable=False),
        sa.Column("breakeven", sa.Boolean(), nullable=False),
        sa.Column("facts_payload", sa.JSON(), nullable=False),
        sa.Column("narrative_explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(evidence_window_hash) = 64",
            name="learning_attribution_records_window_hash_len",
        ),
        sa.CheckConstraint(
            "length(uniqueness_tuple_hash) = 64",
            name="learning_attribution_records_uniqueness_len",
        ),
        sa.CheckConstraint(
            "length(candidate_content_hash) = 64",
            name="learning_attribution_records_candidate_hash_len",
        ),
        sa.CheckConstraint(
            "length(facts_hash) = 64",
            name="learning_attribution_records_facts_hash_len",
        ),
        sa.CheckConstraint(
            "learning_venue_mode IN ('paper_internal', 'paper_exchange_demo')",
            name="learning_attribution_records_venue_mode",
        ),
        sa.CheckConstraint(
            "(NOT executed_trade_outcome) OR (journal_trade_id IS NOT NULL)",
            name="learning_attribution_records_executed_has_trade",
        ),
        sa.CheckConstraint(
            "NOT (executed_trade_outcome AND rejected)",
            name="learning_attribution_records_reject_not_executed",
        ),
        sa.CheckConstraint(
            "NOT (executed_trade_outcome AND skipped)",
            name="learning_attribution_records_skip_not_executed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_learning_attr_records_org",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_learning_attr_records_user",
        ),
        sa.ForeignKeyConstraint(
            ["journal_trade_id"],
            ["journal_trades.id"],
            name="fk_learning_attr_records_journal_trade",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_learning_attribution_records"),
        sa.UniqueConstraint(
            "organization_id",
            "candidate_id",
            name="uq_learning_attribution_records_org_candidate",
        ),
    )
    op.create_index(
        "uq_learning_attribution_records_org_lifecycle",
        "learning_attribution_records",
        ["organization_id", "execution_lifecycle_id"],
        unique=True,
        postgresql_where=sa.text("execution_lifecycle_id IS NOT NULL"),
        sqlite_where=sa.text("execution_lifecycle_id IS NOT NULL"),
    )
    op.create_index(
        "ix_learning_attribution_records_org_strategy_setup",
        "learning_attribution_records",
        [
            "organization_id",
            "strategy_version_id",
            "setup_definition_id",
            "learning_venue_mode",
        ],
    )
    op.create_index(
        "ix_learning_attribution_records_org_venue",
        "learning_attribution_records",
        ["organization_id", "learning_venue_mode"],
    )

    op.create_table(
        "learning_attribution_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attribution_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("event_index", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("source_aggregate", sa.String(length=160), nullable=False),
        sa.Column("source_event_id", sa.String(length=160), nullable=False),
        sa.Column("source_event_version", sa.Integer(), nullable=False),
        sa.Column("supersession", sa.Integer(), nullable=False),
        sa.Column("event_content_hash", sa.String(length=64), nullable=False),
        sa.Column("facts_hash", sa.String(length=64), nullable=False),
        sa.Column("journal_trade_id", sa.Uuid(), nullable=True),
        sa.Column("payload_lineage", sa.JSON(), nullable=False),
        sa.Column("projection", sa.JSON(), nullable=False),
        sa.Column("narrative_explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(event_content_hash) = 64",
            name="learning_attribution_events_event_hash_len",
        ),
        sa.CheckConstraint(
            "length(facts_hash) = 64",
            name="learning_attribution_events_facts_hash_len",
        ),
        sa.CheckConstraint(
            "event_index >= 1",
            name="learning_attribution_events_index_min",
        ),
        sa.ForeignKeyConstraint(
            ["attribution_id"],
            ["learning_attribution_records.id"],
            name="fk_learning_attr_events_record",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_learning_attr_events_org",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_learning_attribution_events"),
        sa.UniqueConstraint(
            "organization_id",
            "account_id",
            "source_system",
            "source_aggregate",
            "event_type",
            "source_event_id",
            "source_event_version",
            "supersession",
            name="uq_learning_attribution_events_source",
        ),
        sa.UniqueConstraint(
            "attribution_id",
            "event_index",
            name="uq_learning_attribution_events_index",
        ),
    )
    op.create_index(
        "ix_learning_attribution_events_org_attribution",
        "learning_attribution_events",
        ["organization_id", "attribution_id", "event_index"],
    )

    if _is_postgres():
        for statement in historical_immutability_phase8_install_statements():
            op.execute(statement)
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {_IDENTITY_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
              IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
                 OR NEW.candidate_id IS DISTINCT FROM OLD.candidate_id
                 OR NEW.assessment_id IS DISTINCT FROM OLD.assessment_id
                 OR NEW.evidence_window_hash IS DISTINCT FROM OLD.evidence_window_hash
                 OR NEW.uniqueness_tuple_hash IS DISTINCT FROM OLD.uniqueness_tuple_hash
                 OR NEW.learning_venue_mode IS DISTINCT FROM OLD.learning_venue_mode
              THEN
                RAISE EXCEPTION 'learning attribution identity is immutable';
              END IF;
              IF OLD.execution_lifecycle_id IS NOT NULL
                 AND NEW.execution_lifecycle_id IS DISTINCT FROM OLD.execution_lifecycle_id
              THEN
                RAISE EXCEPTION 'learning attribution lifecycle binding is sticky';
              END IF;
              IF OLD.journal_trade_id IS NOT NULL
                 AND NEW.journal_trade_id IS DISTINCT FROM OLD.journal_trade_id
              THEN
                RAISE EXCEPTION 'learning attribution journal trade binding is sticky';
              END IF;
              RETURN NEW;
            END;
            $$;
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER {_IDENTITY_TRIGGER}
            BEFORE UPDATE ON learning_attribution_records
            FOR EACH ROW EXECUTE PROCEDURE {_IDENTITY_FUNCTION}();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT COUNT(*) FROM learning_attribution_records")).scalar()
    if int(count or 0) > 0:
        raise RuntimeError("Cannot downgrade while learning attribution rows exist.")

    if _is_postgres():
        op.execute(f"DROP TRIGGER IF EXISTS {_IDENTITY_TRIGGER} ON learning_attribution_records")
        op.execute(f"DROP TRIGGER IF EXISTS {_EVENT_TRIGGER} ON learning_attribution_events")
        op.execute(f"DROP FUNCTION IF EXISTS {_IDENTITY_FUNCTION}()")

    op.drop_index(
        "ix_learning_attribution_events_org_attribution",
        table_name="learning_attribution_events",
    )
    op.drop_table("learning_attribution_events")
    op.drop_index(
        "ix_learning_attribution_records_org_venue",
        table_name="learning_attribution_records",
    )
    op.drop_index(
        "ix_learning_attribution_records_org_strategy_setup",
        table_name="learning_attribution_records",
    )
    op.drop_index(
        "uq_learning_attribution_records_org_lifecycle",
        table_name="learning_attribution_records",
    )
    op.drop_table("learning_attribution_records")
    op.drop_index("ix_journal_trades_org_candidate", table_name="journal_trades")
    op.drop_constraint(
        "ck_journal_trades_lineage_window_hash",
        "journal_trades",
        type_="check",
    )
    op.drop_column("journal_trades", "trade_plan_revision_id")
    op.drop_column("journal_trades", "evidence_window_hash")
    op.drop_column("journal_trades", "assessment_id")
    op.drop_column("journal_trades", "candidate_id")
