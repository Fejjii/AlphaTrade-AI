"""Slice 24 — billing-grade usage fields and organization quotas."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g7h8i9j0k1l2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usage_events",
        sa.Column("provider_reported_cost", sa.Numeric(20, 8), nullable=True),
    )
    op.add_column(
        "usage_events",
        sa.Column(
            "cost_source",
            sa.String(40),
            nullable=False,
            server_default="unavailable",
        ),
    )
    op.execute(
        "UPDATE usage_events SET cost_source = 'static_estimated' "
        "WHERE cost_is_placeholder = true AND total_tokens > 0"
    )
    op.execute(
        "UPDATE usage_events SET cost_source = 'provider_reported', cost_is_placeholder = false "
        "WHERE cost_is_placeholder = false"
    )

    op.create_table(
        "organization_quotas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("monthly_token_limit", sa.Integer(), nullable=False, server_default="2000000"),
        sa.Column("monthly_cost_limit", sa.Numeric(20, 8), nullable=False, server_default="100"),
        sa.Column("daily_request_limit", sa.Integer(), nullable=False, server_default="5000"),
        sa.Column("limit_agent_chat", sa.Integer(), nullable=False, server_default="2000"),
        sa.Column("limit_rag_ingest", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("limit_market_analyze", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("limit_agent_narrative", sa.Integer(), nullable=False, server_default="2000"),
        sa.Column("limit_paper_execution", sa.Integer(), nullable=False, server_default="200"),
        sa.Column(
            "soft_warning_threshold",
            sa.Numeric(20, 8),
            nullable=False,
            server_default="0.80",
        ),
        sa.Column(
            "hard_block_threshold",
            sa.Numeric(20, 8),
            nullable=False,
            server_default="1.00",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
    )


def downgrade() -> None:
    op.drop_table("organization_quotas")
    op.drop_column("usage_events", "cost_source")
    op.drop_column("usage_events", "provider_reported_cost")
