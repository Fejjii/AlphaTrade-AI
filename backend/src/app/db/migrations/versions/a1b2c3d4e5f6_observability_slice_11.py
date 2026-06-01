"""Observability slice 11 — audit and usage columns.

Revision ID: a1b2c3d4e5f6
Revises: 7bad3454d0e4
Create Date: 2026-06-01

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "7bad3454d0e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("trace_id", sa.String(length=64), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column("actor_type", sa.String(length=32), nullable=False, server_default="system"),
    )
    op.add_column(
        "audit_logs",
        sa.Column("result", sa.String(length=32), nullable=False, server_default="success"),
    )
    op.add_column(
        "audit_logs",
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="info"),
    )
    op.add_column("audit_logs", sa.Column("payload_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column("redacted_metadata", sa.JSON(), nullable=False, server_default="{}"),
    )

    op.add_column("usage_events", sa.Column("request_id", sa.String(length=64), nullable=True))
    op.add_column(
        "usage_events",
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "usage_events",
        sa.Column("cost_is_placeholder", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.add_column(
        "usage_events",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
    )


def downgrade() -> None:
    op.drop_column("usage_events", "status")
    op.drop_column("usage_events", "cost_is_placeholder")
    op.drop_column("usage_events", "total_tokens")
    op.drop_column("usage_events", "request_id")
    op.drop_column("audit_logs", "redacted_metadata")
    op.drop_column("audit_logs", "payload_hash")
    op.drop_column("audit_logs", "severity")
    op.drop_column("audit_logs", "result")
    op.drop_column("audit_logs", "actor_type")
    op.drop_column("audit_logs", "trace_id")
