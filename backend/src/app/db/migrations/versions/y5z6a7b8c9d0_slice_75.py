"""Slice 75 — persist market watcher scan summaries."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "y5z6a7b8c9d0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_watcher_scan_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.String(length=255), nullable=True),
        sa.Column("alerts_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alerts_deduped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conditions_found", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("symbols", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("timeframes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("detectors_enabled", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("detector_versions", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_watcher_scan_records_org_scanned",
        "market_watcher_scan_records",
        ["organization_id", "scanned_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_watcher_scan_records_org_scanned")
    op.drop_table("market_watcher_scan_records")
