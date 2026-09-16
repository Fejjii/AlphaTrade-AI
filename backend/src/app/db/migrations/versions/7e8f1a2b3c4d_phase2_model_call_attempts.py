"""phase 2 model call telemetry

Revision ID: 7e8f1a2b3c4d
Revises: 6d4e9f0a12b3
Create Date: 2026-09-16 07:50:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7e8f1a2b3c4d"
down_revision: str | None = "6d4e9f0a12b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "model_call_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("usage_event_id", sa.Uuid(), nullable=True),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("tier", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("requested_model", sa.String(length=80), nullable=False),
        sa.Column("resolved_model", sa.String(length=80), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("fallback_policy", sa.String(length=40), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_category", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("cost_source", sa.String(length=40), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("retention_category", sa.String(length=40), nullable=False),
        sa.Column("mutation_allowed", sa.Boolean(), nullable=False),
        sa.Column("started_at", _TS, nullable=False),
        sa.Column("completed_at", _TS, nullable=False),
        sa.Column("event_at", _TS, nullable=False),
        sa.Column("created_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["usage_event_id"], ["usage_events.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_model_call_attempts"),
        sa.CheckConstraint("length(policy_version) > 0", name="ck_model_call_policy_version"),
        sa.CheckConstraint("NOT mutation_allowed", name="ck_model_call_no_mutation"),
    )
    op.create_index(
        "ix_model_call_attempts_correlation",
        "model_call_attempts",
        ["correlation_id"],
    )
    op.create_index(
        "ix_model_call_attempts_org_event",
        "model_call_attempts",
        ["organization_id", "event_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_model_call_attempts_org_event", table_name="model_call_attempts")
    op.drop_index("ix_model_call_attempts_correlation", table_name="model_call_attempts")
    op.drop_table("model_call_attempts")
