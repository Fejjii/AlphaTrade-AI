"""observed watcher and telegram runtime status

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-09-22 21:40:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e0f1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "controlled_runtime_status",
        sa.Column("component", sa.String(length=32), nullable=False),
        sa.Column("worker_id", sa.String(length=80), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activation_state", sa.String(length=32), nullable=False),
        sa.Column("lease_owner", sa.String(length=80), nullable=False),
        sa.Column("lease_epoch", sa.Integer(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fence_held", sa.Boolean(), nullable=False),
        sa.Column("last_scan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scan_reason", sa.String(length=64), nullable=False),
        sa.Column("market_source", sa.String(length=32), nullable=False),
        sa.Column("freshness_seconds", sa.Float(), nullable=True),
        sa.Column("telegram_runtime_state", sa.String(length=32), nullable=False),
        sa.Column("inbound_mode", sa.String(length=16), nullable=False),
        sa.Column("outbox_pending", sa.Integer(), nullable=False),
        sa.Column("outbox_retryable", sa.Integer(), nullable=False),
        sa.Column("outbox_dead_letter", sa.Integer(), nullable=False),
        sa.Column("last_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=False),
        sa.Column("kill_switch_active", sa.Boolean(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("request_weight", sa.Integer(), nullable=False),
        sa.Column("rate_limited_count", sa.Integer(), nullable=False),
        sa.Column("cache_hits", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("component", name=op.f("pk_controlled_runtime_status")),
    )


def downgrade() -> None:
    op.drop_table("controlled_runtime_status")
