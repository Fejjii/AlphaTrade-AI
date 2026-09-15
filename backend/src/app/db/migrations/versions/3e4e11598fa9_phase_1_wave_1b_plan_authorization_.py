"""phase 1 wave 1b plan authorization payload

Revision ID: 3e4e11598fa9
Revises: p2e3f4a5b6c7
Create Date: 2026-09-15 14:48:46.542432
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "3e4e11598fa9"
down_revision: str | None = "p2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_exchange_account_tenant_owner",
        "exchange_accounts",
        ["id", "organization_id", "user_id"],
    )
    op.create_unique_constraint(
        "uq_trade_proposal_tenant_owner",
        "trade_proposals",
        ["id", "organization_id", "user_id"],
    )
    op.create_table(
        "execution_accounts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "execution_mode",
            sa.Enum("PAPER", name="executionmode", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column(
            "account_mode",
            sa.Enum("NET", name="accountmode", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("account_mode = 'NET'", name="ck_execution_account_net"),
        sa.CheckConstraint("execution_mode = 'PAPER'", name="ck_execution_account_paper"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "user_id",
            name="uq_execution_account_tenant_owner",
        ),
    )
    op.create_table(
        "trade_plan_revisions",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("exchange_account_id", sa.Uuid(), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column(
            "operation",
            sa.Enum("SUBMIT_ENTRY", name="planoperation", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=False),
        sa.Column("setup_definition_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column(
            "expected_account_mode",
            sa.Enum("NET", name="accountmode", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("permission_attestation_id", sa.Uuid(), nullable=False),
        sa.Column("permission_attestation_version", sa.String(length=64), nullable=False),
        sa.Column("execution_venue", sa.String(length=40), nullable=False),
        sa.Column("execution_instrument", sa.String(length=120), nullable=False),
        sa.Column("execution_policy_version", sa.String(length=64), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("semantic_payload", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("presentation_metadata", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(content_hash) = 64",
            name="ck_plan_content_hash_length",
        ),
        sa.CheckConstraint(
            "expected_account_mode = 'NET'",
            name="ck_plan_expected_net",
        ),
        sa.CheckConstraint(
            "operation = 'SUBMIT_ENTRY'",
            name="ck_plan_submit_entry",
        ),
        sa.CheckConstraint(
            "schema_version = 'CanonicalTradePlanContentV1'",
            name="ck_plan_schema_v1",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "organization_id", "user_id"],
            [
                "execution_accounts.id",
                "execution_accounts.organization_id",
                "execution_accounts.user_id",
            ],
            name="fk_trade_plan_revision_account_tenant",
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["paper_validation_candidates.id"]),
        sa.ForeignKeyConstraint(
            ["exchange_account_id", "organization_id", "user_id"],
            [
                "exchange_accounts.id",
                "exchange_accounts.organization_id",
                "exchange_accounts.user_id",
            ],
            name="fk_trade_plan_revision_exchange_account_tenant",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["plan_id", "organization_id", "user_id"],
            [
                "trade_proposals.id",
                "trade_proposals.organization_id",
                "trade_proposals.user_id",
            ],
            name="fk_trade_plan_revision_plan_tenant",
        ),
        sa.ForeignKeyConstraint(["setup_definition_id"], ["setup_definitions.id"]),
        sa.ForeignKeyConstraint(["strategy_version_id"], ["user_strategy_versions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash"),
        sa.UniqueConstraint(
            "id",
            "plan_id",
            "organization_id",
            "user_id",
            "account_id",
            name="uq_trade_plan_revision_binding",
        ),
    )
    op.create_index(
        "ix_trade_plan_revisions_plan_created",
        "trade_plan_revisions",
        ["organization_id", "plan_id", "created_at"],
    )
    op.add_column(
        "trade_proposals",
        sa.Column("latest_plan_revision_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_trade_proposals_latest_plan_revision",
        "trade_proposals",
        "trade_plan_revisions",
        ["latest_plan_revision_id"],
        ["id"],
    )

    op.drop_constraint("uq_approvals_proposal_id", "approvals", type_="unique")
    op.add_column("approvals", sa.Column("plan_revision_id", sa.Uuid(), nullable=True))
    op.add_column(
        "approvals",
        sa.Column("authorization_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_approvals_plan_revision",
        "approvals",
        "trade_plan_revisions",
        ["plan_revision_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_approvals_plan_revision_id",
        "approvals",
        ["plan_revision_id"],
    )

    op.create_table(
        "approval_authorizations",
        sa.Column("approval_request_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("exchange_account_id", sa.Uuid(), nullable=True),
        sa.Column("exchange_account_scope_key", sa.String(length=36), nullable=False),
        sa.Column(
            "operation",
            sa.Enum("SUBMIT_ENTRY", name="planoperation", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column(
            "execution_mode",
            sa.Enum("PAPER", name="executionmode", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("plan_content_hash", sa.String(length=64), nullable=False),
        sa.Column("execution_venue", sa.String(length=40), nullable=False),
        sa.Column("execution_instrument", sa.String(length=120), nullable=False),
        sa.Column(
            "verified_account_mode",
            sa.Enum("NET", name="accountmode", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("permission_attestation_id", sa.Uuid(), nullable=False),
        sa.Column("permission_attestation_version", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "AVAILABLE",
                "CONSUMED",
                "REVOKED",
                "EXPIRED",
                name="authorizationstate",
                native_enum=False,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.Enum(
                "WEB",
                "API",
                "TELEGRAM",
                name="authorizationchannel",
                native_enum=False,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_by_execution_command_id", sa.Uuid(), nullable=True),
        sa.Column("authorization_content_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(authorization_content_hash) = 64",
            name="ck_authorization_content_hash_length",
        ),
        sa.CheckConstraint(
            "length(plan_content_hash) = 64",
            name="ck_authorization_plan_hash_length",
        ),
        sa.CheckConstraint(
            "execution_mode = 'PAPER'",
            name="ck_authorization_paper",
        ),
        sa.CheckConstraint(
            "operation = 'SUBMIT_ENTRY'",
            name="ck_authorization_submit_entry",
        ),
        sa.CheckConstraint(
            "verified_account_mode = 'NET'",
            name="ck_authorization_verified_net",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["execution_accounts.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approvals.id"]),
        sa.ForeignKeyConstraint(
            ["exchange_account_id", "organization_id", "user_id"],
            [
                "exchange_accounts.id",
                "exchange_accounts.organization_id",
                "exchange_accounts.user_id",
            ],
            name="fk_approval_authorization_exchange_account_tenant",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["revision_id", "plan_id", "organization_id", "user_id", "account_id"],
            [
                "trade_plan_revisions.id",
                "trade_plan_revisions.plan_id",
                "trade_plan_revisions.organization_id",
                "trade_plan_revisions.user_id",
                "trade_plan_revisions.account_id",
            ],
            name="fk_approval_authorization_revision_binding",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_request_id"),
        sa.UniqueConstraint("authorization_content_hash"),
    )
    op.create_index(
        "uq_available_approval_authorization",
        "approval_authorizations",
        [
            "organization_id",
            "account_id",
            "exchange_account_scope_key",
            "revision_id",
            "plan_content_hash",
            "operation",
        ],
        unique=True,
        postgresql_where=sa.text("state = 'AVAILABLE'"),
        sqlite_where=sa.text("state = 'AVAILABLE'"),
    )
    _create_immutability_triggers()


def downgrade() -> None:
    _drop_immutability_triggers()
    op.drop_index(
        "uq_available_approval_authorization",
        table_name="approval_authorizations",
    )
    op.drop_table("approval_authorizations")

    op.drop_constraint("uq_approvals_plan_revision_id", "approvals", type_="unique")
    op.drop_constraint("fk_approvals_plan_revision", "approvals", type_="foreignkey")
    op.create_unique_constraint(
        "uq_approvals_proposal_id",
        "approvals",
        ["proposal_id"],
    )
    op.drop_column("approvals", "authorization_expires_at")
    op.drop_column("approvals", "plan_revision_id")

    op.drop_constraint(
        "fk_trade_proposals_latest_plan_revision",
        "trade_proposals",
        type_="foreignkey",
    )
    op.drop_column("trade_proposals", "latest_plan_revision_id")
    op.drop_index(
        "ix_trade_plan_revisions_plan_created",
        table_name="trade_plan_revisions",
    )
    op.drop_table("trade_plan_revisions")
    op.drop_table("execution_accounts")
    op.drop_constraint(
        "uq_trade_proposal_tenant_owner",
        "trade_proposals",
        type_="unique",
    )
    op.drop_constraint(
        "uq_exchange_account_tenant_owner",
        "exchange_accounts",
        type_="unique",
    )


def _create_immutability_triggers() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION reject_trade_plan_revision_mutation()
            RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'TradePlanRevision rows are immutable';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER trade_plan_revision_no_mutation
            BEFORE UPDATE OR DELETE ON trade_plan_revisions
            FOR EACH ROW EXECUTE FUNCTION reject_trade_plan_revision_mutation()
            """
        )
    elif dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER trade_plan_revision_no_update
            BEFORE UPDATE ON trade_plan_revisions
            BEGIN
              SELECT RAISE(ABORT, 'TradePlanRevision rows are immutable');
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER trade_plan_revision_no_delete
            BEFORE DELETE ON trade_plan_revisions
            BEGIN
              SELECT RAISE(ABORT, 'TradePlanRevision rows are immutable');
            END
            """
        )


def _drop_immutability_triggers() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trade_plan_revision_no_mutation ON trade_plan_revisions"
        )
        op.execute("DROP FUNCTION IF EXISTS reject_trade_plan_revision_mutation()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trade_plan_revision_no_update")
        op.execute("DROP TRIGGER IF EXISTS trade_plan_revision_no_delete")
