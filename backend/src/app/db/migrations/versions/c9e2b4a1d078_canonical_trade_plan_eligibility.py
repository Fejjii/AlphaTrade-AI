"""canonical trade plan and action eligibility postgres binding

Revision ID: c9e2b4a1d078
Revises: 4fd8c1a90b27
Create Date: 2026-09-19 07:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9e2b4a1d078"
down_revision: str | None = "4fd8c1a90b27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APPEND_ONLY_FUNCTION = "alphatrade_forbid_canonical_plan_history_mutation"
_ELIGIBILITY_TRIGGER = "trg_action_eligibility_evaluations_append_only"
_BINDING_TRIGGER = "trg_action_eligibility_identity_bindings_append_only"
_ROOT_TRIGGER = "trg_canonical_trade_plan_roots_append_only"
_LINEAGE_TRIGGER = "trg_canonical_trade_plan_lineage_append_only"
_IDEM_TRIGGER = "trg_canonical_trade_plan_idempotency_keys_append_only"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _drop_fk_to(table_name: str, referred_table: str) -> None:
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(table_name):
        if foreign_key.get("referred_table") == referred_table and foreign_key.get("name"):
            op.drop_constraint(foreign_key["name"], table_name, type_="foreignkey")


def upgrade() -> None:
    _drop_fk_to("trade_plan_revisions", "paper_validation_candidates")
    _drop_fk_to("trade_plan_revisions", "setup_definitions")

    op.add_column(
        "trade_proposals",
        sa.Column(
            "plan_root_kind",
            sa.String(length=32),
            nullable=False,
            server_default="analysis_proposal",
        ),
    )
    op.create_check_constraint(
        "ck_trade_proposals_plan_root_kind",
        "trade_proposals",
        "plan_root_kind IN ('analysis_proposal', 'canonical_plan_root')",
    )

    op.add_column(
        "trade_plan_revisions",
        sa.Column(
            "plan_authority",
            sa.String(length=32),
            nullable=False,
            server_default="paper_validation",
        ),
    )
    op.add_column(
        "trade_plan_revisions",
        sa.Column("canonical_candidate_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "trade_plan_revisions",
        sa.Column("compiled_setup_definition_id", sa.Uuid(), nullable=True),
    )
    op.create_check_constraint(
        "ck_tpr_plan_authority",
        "trade_plan_revisions",
        "plan_authority IN ('paper_validation', 'canonical')",
    )
    op.create_check_constraint(
        "ck_tpr_canonical_candidate_bind",
        "trade_plan_revisions",
        "(plan_authority = 'paper_validation' AND canonical_candidate_id IS NULL) OR "
        "(plan_authority = 'canonical' AND canonical_candidate_id IS NOT NULL "
        "AND canonical_candidate_id = candidate_id)",
    )
    op.create_check_constraint(
        "ck_tpr_compiled_setup_bind",
        "trade_plan_revisions",
        "(plan_authority = 'paper_validation' AND compiled_setup_definition_id IS NULL) OR "
        "(plan_authority = 'canonical' AND compiled_setup_definition_id IS NOT NULL "
        "AND compiled_setup_definition_id = setup_definition_id)",
    )
    op.create_foreign_key(
        "fk_tpr_canonical_candidate",
        "trade_plan_revisions",
        "canonical_candidates",
        ["canonical_candidate_id"],
        ["candidate_id"],
    )
    op.create_foreign_key(
        "fk_tpr_compiled_setup",
        "trade_plan_revisions",
        "compiled_setup_definitions",
        ["compiled_setup_definition_id"],
        ["id"],
    )

    op.create_table(
        "action_eligibility_evaluations",
        sa.Column("eligibility_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_revision", sa.Integer(), nullable=False),
        sa.Column("uniqueness_hash", sa.String(length=64), nullable=False),
        sa.Column("evaluation_revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("paper_actionable", sa.Boolean(), nullable=False),
        sa.Column("live_executable", sa.Boolean(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evaluation_revision >= 1",
            name="action_eligibility_evaluations_revision_min",
        ),
        sa.CheckConstraint(
            "length(uniqueness_hash) = 64",
            name="action_eligibility_evaluations_uniqueness_len",
        ),
        sa.CheckConstraint(
            "length(content_hash) = 64",
            name="action_eligibility_evaluations_content_hash_len",
        ),
        sa.CheckConstraint(
            "live_executable = false",
            name="action_eligibility_evaluations_not_live",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["canonical_candidates.candidate_id"],
            name="fk_eligibility_candidate",
        ),
        sa.PrimaryKeyConstraint("eligibility_id", name="pk_action_eligibility_evaluations"),
        sa.UniqueConstraint("uniqueness_hash", name="uq_action_eligibility_evaluations_hash"),
        sa.UniqueConstraint(
            "organization_id",
            "account_id",
            "candidate_id",
            "evaluation_revision",
            name="uq_action_eligibility_evaluations_lineage_revision",
        ),
    )
    op.create_index(
        "ix_action_eligibility_evaluations_org_account_candidate",
        "action_eligibility_evaluations",
        ["organization_id", "account_id", "candidate_id", "evaluation_revision"],
        unique=False,
    )

    op.create_table(
        "action_eligibility_identity_bindings",
        sa.Column("binding_kind", sa.String(length=32), nullable=False),
        sa.Column("binding_key", sa.String(length=220), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "length(fingerprint) = 64",
            name="action_eligibility_identity_bindings_fingerprint_len",
        ),
        sa.PrimaryKeyConstraint(
            "binding_kind",
            "binding_key",
            name="pk_action_eligibility_identity_bindings",
        ),
    )

    op.create_table(
        "canonical_trade_plan_roots",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["canonical_candidates.candidate_id"],
            name="fk_canonical_plan_root_candidate",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id", "organization_id", "user_id"],
            ["trade_proposals.id", "trade_proposals.organization_id", "trade_proposals.user_id"],
            name="fk_canonical_plan_root_proposal",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "organization_id", "user_id"],
            [
                "execution_accounts.id",
                "execution_accounts.organization_id",
                "execution_accounts.user_id",
            ],
            name="fk_canonical_plan_root_account",
        ),
        sa.PrimaryKeyConstraint("plan_id", name="pk_canonical_trade_plan_roots"),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            "account_id",
            "candidate_id",
            name="uq_canonical_trade_plan_roots_scope",
        ),
    )

    op.create_table(
        "canonical_trade_plan_lineage",
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_revision", sa.Integer(), nullable=False),
        sa.Column("candidate_content_hash", sa.String(length=64), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("eligibility_id", sa.Uuid(), nullable=False),
        sa.Column("eligibility_content_hash", sa.String(length=64), nullable=False),
        sa.Column("eligibility_uniqueness_hash", sa.String(length=64), nullable=False),
        sa.Column("evidence_window_hash", sa.String(length=64), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=False),
        sa.Column("setup_definition_id", sa.Uuid(), nullable=False),
        sa.Column("compiled_setup_content_hash", sa.String(length=64), nullable=False),
        sa.Column("fusion_policy_version", sa.String(length=120), nullable=False),
        sa.Column("uniqueness_hash", sa.String(length=64), nullable=False),
        sa.Column("envelope_content_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "length(uniqueness_hash) = 64",
            name="canonical_trade_plan_lineage_uniqueness_len",
        ),
        sa.CheckConstraint(
            "length(envelope_content_hash) = 64",
            name="canonical_trade_plan_lineage_envelope_len",
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["trade_plan_revisions.id"],
            name="fk_canonical_plan_lineage_revision",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["canonical_candidates.candidate_id"],
            name="fk_canonical_plan_lineage_candidate",
        ),
        sa.ForeignKeyConstraint(
            ["eligibility_id"],
            ["action_eligibility_evaluations.eligibility_id"],
            name="fk_canonical_plan_lineage_eligibility",
        ),
        sa.PrimaryKeyConstraint("revision_id", name="pk_canonical_trade_plan_lineage"),
        sa.UniqueConstraint("uniqueness_hash", name="uq_canonical_trade_plan_lineage_hash"),
    )

    op.create_table(
        "canonical_trade_plan_idempotency_keys",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("uniqueness_hash", sa.String(length=64), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "length(uniqueness_hash) = 64",
            name="canonical_trade_plan_idempotency_keys_hash_len",
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["trade_plan_revisions.id"],
            name="fk_canonical_plan_idempotency_revision",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "idempotency_key",
            name="pk_canonical_trade_plan_idempotency_keys",
        ),
    )

    if _is_postgres():
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {_APPEND_ONLY_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
              RAISE EXCEPTION 'canonical plan and eligibility history is append-only';
            END;
            $$;
            """
        )
        for trigger, table in (
            (_ELIGIBILITY_TRIGGER, "action_eligibility_evaluations"),
            (_BINDING_TRIGGER, "action_eligibility_identity_bindings"),
            (_ROOT_TRIGGER, "canonical_trade_plan_roots"),
            (_LINEAGE_TRIGGER, "canonical_trade_plan_lineage"),
            (_IDEM_TRIGGER, "canonical_trade_plan_idempotency_keys"),
        ):
            op.execute(
                f"""
                CREATE TRIGGER {trigger}
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE PROCEDURE {_APPEND_ONLY_FUNCTION}();
                """
            )


def downgrade() -> None:
    if _is_postgres():
        canonical_count = (
            op.get_bind()
            .execute(
                sa.text(
                    "SELECT COUNT(*) FROM trade_plan_revisions WHERE plan_authority = 'canonical'"
                )
            )
            .scalar()
        )
        if int(canonical_count or 0) > 0:
            raise RuntimeError("Cannot downgrade while canonical TradePlanRevision rows exist.")
        for trigger, table in (
            (_IDEM_TRIGGER, "canonical_trade_plan_idempotency_keys"),
            (_LINEAGE_TRIGGER, "canonical_trade_plan_lineage"),
            (_ROOT_TRIGGER, "canonical_trade_plan_roots"),
            (_BINDING_TRIGGER, "action_eligibility_identity_bindings"),
            (_ELIGIBILITY_TRIGGER, "action_eligibility_evaluations"),
        ):
            op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS {_APPEND_ONLY_FUNCTION}()")

    op.drop_table("canonical_trade_plan_idempotency_keys")
    op.drop_table("canonical_trade_plan_lineage")
    op.drop_table("canonical_trade_plan_roots")
    op.drop_table("action_eligibility_identity_bindings")
    op.drop_index(
        "ix_action_eligibility_evaluations_org_account_candidate",
        table_name="action_eligibility_evaluations",
    )
    op.drop_table("action_eligibility_evaluations")

    op.drop_constraint("fk_tpr_compiled_setup", "trade_plan_revisions", type_="foreignkey")
    op.drop_constraint("fk_tpr_canonical_candidate", "trade_plan_revisions", type_="foreignkey")
    op.drop_constraint("ck_tpr_compiled_setup_bind", "trade_plan_revisions", type_="check")
    op.drop_constraint("ck_tpr_canonical_candidate_bind", "trade_plan_revisions", type_="check")
    op.drop_constraint("ck_tpr_plan_authority", "trade_plan_revisions", type_="check")
    op.drop_column("trade_plan_revisions", "compiled_setup_definition_id")
    op.drop_column("trade_plan_revisions", "canonical_candidate_id")
    op.drop_column("trade_plan_revisions", "plan_authority")

    op.drop_constraint("ck_trade_proposals_plan_root_kind", "trade_proposals", type_="check")
    op.drop_column("trade_proposals", "plan_root_kind")

    op.create_foreign_key(
        "fk_trade_plan_revisions_candidate_id_paper_validation_c_7362",
        "trade_plan_revisions",
        "paper_validation_candidates",
        ["candidate_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_trade_plan_revisions_setup_definition_id_setup_definitions",
        "trade_plan_revisions",
        "setup_definitions",
        ["setup_definition_id"],
        ["id"],
    )
