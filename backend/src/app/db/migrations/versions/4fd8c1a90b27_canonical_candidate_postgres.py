"""canonical candidate postgres persistence

Revision ID: 4fd8c1a90b27
Revises: 3ec264f9aaa8
Create Date: 2026-09-18 22:24:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "4fd8c1a90b27"
down_revision: str | None = "3ec264f9aaa8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APPEND_ONLY_FUNCTION = "alphatrade_forbid_canonical_candidate_history_mutation"
_CANDIDATE_DELETE_TRIGGER = "trg_canonical_candidates_no_delete"
_CREATION_KEY_TRIGGER = "trg_canonical_candidate_creation_keys_append_only"
_TRANSITION_TRIGGER = "trg_canonical_candidate_transitions_append_only"
_TRANSITION_KEY_TRIGGER = "trg_canonical_candidate_transition_keys_append_only"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "canonical_candidates",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("uniqueness_hash", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=False),
        sa.Column("setup_definition_id", sa.Uuid(), nullable=False),
        sa.Column("fusion_policy_version", sa.String(length=120), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("evidence_venue", sa.String(length=64), nullable=False),
        sa.Column("evidence_market", sa.String(length=64), nullable=False),
        sa.Column("evidence_instrument", sa.String(length=80), nullable=False),
        sa.Column("timeframe", sa.String(length=32), nullable=False),
        sa.Column("evidence_window_hash", sa.String(length=64), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("executable_setup", sa.JSON(), nullable=False),
        sa.Column("evidence_identity", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transition_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "transition_version >= 1",
            name="canonical_candidates_version_min",
        ),
        sa.CheckConstraint(
            "length(uniqueness_hash) = 64",
            name="canonical_candidates_uniqueness_len",
        ),
        sa.CheckConstraint(
            "length(evidence_window_hash) = 64",
            name="canonical_candidates_window_hash_len",
        ),
        sa.CheckConstraint(
            "length(content_hash) = 64",
            name="canonical_candidates_content_hash_len",
        ),
        sa.PrimaryKeyConstraint("candidate_id", name=op.f("pk_canonical_candidates")),
        sa.UniqueConstraint(
            "organization_id",
            "candidate_id",
            name="uq_canonical_candidates_org_candidate",
        ),
        sa.UniqueConstraint("uniqueness_hash", name="uq_canonical_candidates_uniqueness_hash"),
        sa.UniqueConstraint(
            "organization_id",
            "strategy_version_id",
            "setup_definition_id",
            "fusion_policy_version",
            "direction",
            "evidence_venue",
            "evidence_market",
            "evidence_instrument",
            "timeframe",
            "evidence_window_hash",
            name="uq_canonical_candidates_semantic_key",
        ),
    )
    op.create_index(
        "ix_canonical_candidates_org_state",
        "canonical_candidates",
        ["organization_id", "state"],
        unique=False,
    )
    op.create_table(
        "canonical_candidate_creation_keys",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("uniqueness_hash", sa.String(length=64), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "length(uniqueness_hash) = 64",
            name="canonical_candidate_creation_keys_hash_len",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["canonical_candidates.candidate_id"],
            name="fk_cand_creation_keys_candidate",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "idempotency_key",
            name=op.f("pk_canonical_candidate_creation_keys"),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_canonical_candidate_creation_keys_org_key",
        ),
    )
    op.create_index(
        "ix_canonical_candidate_creation_keys_candidate",
        "canonical_candidate_creation_keys",
        ["candidate_id"],
        unique=False,
    )
    op.create_table(
        "canonical_candidate_transitions",
        sa.Column("transition_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("previous_state", sa.String(length=32), nullable=False),
        sa.Column("new_state", sa.String(length=32), nullable=False),
        sa.Column("transition_version", sa.Integer(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "transition_version >= 1",
            name="canonical_candidate_transitions_version_min",
        ),
        sa.CheckConstraint(
            "length(content_hash) = 64",
            name="canonical_candidate_transitions_hash_len",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["canonical_candidates.candidate_id"],
            name="fk_cand_transitions_candidate",
        ),
        sa.PrimaryKeyConstraint("transition_id", name=op.f("pk_canonical_candidate_transitions")),
        sa.UniqueConstraint(
            "candidate_id",
            "transition_version",
            name="uq_canonical_candidate_transitions_version",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "transition_id",
            name="uq_canonical_candidate_transitions_org_id",
        ),
    )
    op.create_index(
        "ix_canonical_candidate_transitions_org_candidate",
        "canonical_candidate_transitions",
        ["organization_id", "candidate_id", "transition_version"],
        unique=False,
    )
    op.create_table(
        "canonical_candidate_transition_keys",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("transition_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["canonical_candidates.candidate_id"],
            name="fk_cand_tr_keys_candidate",
        ),
        sa.ForeignKeyConstraint(
            ["transition_id"],
            ["canonical_candidate_transitions.transition_id"],
            name="fk_cand_tr_keys_transition",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "candidate_id",
            "idempotency_key",
            name=op.f("pk_canonical_candidate_transition_keys"),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "candidate_id",
            "idempotency_key",
            name="uq_canonical_candidate_transition_keys_org_cand_key",
        ),
    )
    op.create_index(
        "ix_canonical_candidate_transition_keys_transition",
        "canonical_candidate_transition_keys",
        ["transition_id"],
        unique=False,
    )
    if _is_postgres():
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {_APPEND_ONLY_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
              RAISE EXCEPTION 'canonical candidate history is append-only';
            END;
            $$;
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER {_CANDIDATE_DELETE_TRIGGER}
            BEFORE DELETE ON canonical_candidates
            FOR EACH ROW EXECUTE PROCEDURE {_APPEND_ONLY_FUNCTION}();
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER {_CREATION_KEY_TRIGGER}
            BEFORE UPDATE OR DELETE ON canonical_candidate_creation_keys
            FOR EACH ROW EXECUTE PROCEDURE {_APPEND_ONLY_FUNCTION}();
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER {_TRANSITION_TRIGGER}
            BEFORE UPDATE OR DELETE ON canonical_candidate_transitions
            FOR EACH ROW EXECUTE PROCEDURE {_APPEND_ONLY_FUNCTION}();
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER {_TRANSITION_KEY_TRIGGER}
            BEFORE UPDATE OR DELETE ON canonical_candidate_transition_keys
            FOR EACH ROW EXECUTE PROCEDURE {_APPEND_ONLY_FUNCTION}();
            """
        )


def downgrade() -> None:
    if _is_postgres():
        op.execute(f"DROP TRIGGER IF EXISTS {_TRANSITION_KEY_TRIGGER} ON canonical_candidate_transition_keys")
        op.execute(f"DROP TRIGGER IF EXISTS {_TRANSITION_TRIGGER} ON canonical_candidate_transitions")
        op.execute(f"DROP TRIGGER IF EXISTS {_CREATION_KEY_TRIGGER} ON canonical_candidate_creation_keys")
        op.execute(f"DROP TRIGGER IF EXISTS {_CANDIDATE_DELETE_TRIGGER} ON canonical_candidates")
        op.execute(f"DROP FUNCTION IF EXISTS {_APPEND_ONLY_FUNCTION}()")
    op.drop_index(
        "ix_canonical_candidate_transition_keys_transition",
        table_name="canonical_candidate_transition_keys",
    )
    op.drop_table("canonical_candidate_transition_keys")
    op.drop_index(
        "ix_canonical_candidate_transitions_org_candidate",
        table_name="canonical_candidate_transitions",
    )
    op.drop_table("canonical_candidate_transitions")
    op.drop_index(
        "ix_canonical_candidate_creation_keys_candidate",
        table_name="canonical_candidate_creation_keys",
    )
    op.drop_table("canonical_candidate_creation_keys")
    op.drop_index("ix_canonical_candidates_org_state", table_name="canonical_candidates")
    op.drop_table("canonical_candidates")
