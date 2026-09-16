"""phase 3 strategy immutability, compiled setups, level revisions

Revision ID: 8a9b0c1d2e3f
Revises: 7e8f1a2b3c4d
Create Date: 2026-09-16 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.historical_immutability import historical_immutability_install_statements

revision: str = "8a9b0c1d2e3f"
down_revision: str | None = "7e8f1a2b3c4d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)
_MONEY = sa.Numeric(precision=20, scale=8)


def upgrade() -> None:
    op.add_column(
        "user_strategy_versions",
        sa.Column("parent_version_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "user_strategy_versions",
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "user_strategy_versions",
        sa.Column("change_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "user_strategy_versions",
        sa.Column(
            "change_source",
            sa.String(length=40),
            nullable=False,
            server_default="CREATE",
        ),
    )
    op.add_column(
        "user_strategy_versions",
        sa.Column("content_diff", sa.JSON(), nullable=True),
    )
    op.add_column(
        "user_strategy_versions",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        "fk_user_strategy_versions_parent_version_id_user_strategy_versions",
        "user_strategy_versions",
        "user_strategy_versions",
        ["parent_version_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_user_strategy_versions_actor_user_id_users",
        "user_strategy_versions",
        "users",
        ["actor_user_id"],
        ["id"],
    )

    op.create_table(
        "global_setup_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("setup_definition_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("strategy_id", sa.String(length=40), nullable=False),
        sa.Column("is_global", sa.Boolean(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("collision_status", sa.String(length=40), nullable=True),
        sa.Column("created_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["setup_definition_id"], ["setup_definitions.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_global_setup_templates"),
        sa.UniqueConstraint("setup_definition_id", name="uq_global_setup_template_source"),
        sa.CheckConstraint("organization_id IS NULL", name="ck_global_setup_template_no_org"),
    )

    op.create_table(
        "compiled_setup_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=False),
        sa.Column("compiler_version", sa.String(length=80), nullable=False),
        sa.Column("grammar_version", sa.String(length=80), nullable=False),
        sa.Column("compiled_ast", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("compile_status", sa.String(length=40), nullable=False),
        sa.Column("created_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["user_strategies.id"]),
        sa.ForeignKeyConstraint(["strategy_version_id"], ["user_strategy_versions.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_compiled_setup_definitions"),
        sa.UniqueConstraint("strategy_version_id", name="uq_compiled_setup_strategy_version"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_compiled_setup_hash_length"),
        sa.CheckConstraint("length(compiler_version) > 0", name="ck_compiled_setup_compiler"),
    )
    op.create_index(
        "ix_compiled_setup_definitions_organization_id",
        "compiled_setup_definitions",
        ["organization_id"],
    )

    op.create_table(
        "strategy_lifecycle_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=False),
        sa.Column("prior_state", sa.String(length=40), nullable=True),
        sa.Column("new_state", sa.String(length=40), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("occurred_at", _TS, nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["user_strategies.id"]),
        sa.ForeignKeyConstraint(["strategy_version_id"], ["user_strategy_versions.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_strategy_lifecycle_events"),
        sa.CheckConstraint("length(event_hash) = 64", name="ck_strategy_lifecycle_hash"),
    )
    op.create_index(
        "ix_strategy_lifecycle_org_strategy",
        "strategy_lifecycle_events",
        ["organization_id", "strategy_id", "occurred_at"],
    )

    op.create_table(
        "setup_migration_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_setup_migration_runs"),
    )

    op.create_table(
        "manual_level_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("level_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("instrument", sa.String(length=30), nullable=False),
        sa.Column("exchange", sa.String(length=40), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=True),
        sa.Column("level_type", sa.String(length=40), nullable=False),
        sa.Column("value", _MONEY, nullable=True),
        sa.Column("price_low", _MONEY, nullable=True),
        sa.Column("price_high", _MONEY, nullable=True),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("supersedes_revision_id", sa.Uuid(), nullable=True),
        sa.Column("effective_at", _TS, nullable=False),
        sa.Column("created_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["supersedes_revision_id"], ["manual_level_revisions.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_manual_level_revisions"),
        sa.UniqueConstraint("level_id", "revision_number", name="uq_manual_level_revision"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_manual_level_revision_hash"),
    )
    op.create_index(
        "ix_manual_level_revision_org_level",
        "manual_level_revisions",
        ["organization_id", "level_id"],
    )
    op.create_index(
        "ix_manual_level_revisions_level_id",
        "manual_level_revisions",
        ["level_id"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for statement in historical_immutability_install_statements():
            op.execute(statement)


def downgrade() -> None:
    op.drop_index("ix_manual_level_revisions_level_id", table_name="manual_level_revisions")
    op.drop_index("ix_manual_level_revision_org_level", table_name="manual_level_revisions")
    op.drop_table("manual_level_revisions")
    op.drop_table("setup_migration_runs")
    op.drop_index("ix_strategy_lifecycle_org_strategy", table_name="strategy_lifecycle_events")
    op.drop_table("strategy_lifecycle_events")
    op.drop_index(
        "ix_compiled_setup_definitions_organization_id",
        table_name="compiled_setup_definitions",
    )
    op.drop_table("compiled_setup_definitions")
    op.drop_table("global_setup_templates")
    op.drop_constraint(
        "fk_user_strategy_versions_actor_user_id_users",
        "user_strategy_versions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_user_strategy_versions_parent_version_id_user_strategy_versions",
        "user_strategy_versions",
        type_="foreignkey",
    )
    op.drop_column("user_strategy_versions", "content_hash")
    op.drop_column("user_strategy_versions", "content_diff")
    op.drop_column("user_strategy_versions", "change_source")
    op.drop_column("user_strategy_versions", "change_reason")
    op.drop_column("user_strategy_versions", "actor_user_id")
    op.drop_column("user_strategy_versions", "parent_version_id")
