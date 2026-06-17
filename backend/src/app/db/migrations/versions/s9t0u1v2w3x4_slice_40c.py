"""Slice 40C — indexes and alert deduplication."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "s9t0u1v2w3x4"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "paper_validation_alerts",
        sa.Column("dedup_key", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_paper_validation_alerts_org_created",
        "paper_validation_alerts",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_paper_validation_alerts_dedup_key",
        "paper_validation_alerts",
        ["organization_id", "dedup_key", "created_at"],
    )
    op.create_index(
        "ix_paper_validation_alerts_read_at",
        "paper_validation_alerts",
        ["organization_id", "read_at"],
    )
    op.create_index(
        "ix_paper_validation_runtime_history_org_started",
        "paper_validation_runtime_history",
        ["organization_id", "started_at"],
    )
    op.create_index(
        "ix_paper_validation_runtime_history_run_created",
        "paper_validation_runtime_history",
        ["run_id", "created_at"],
    )
    op.create_index(
        "ix_paper_validation_observability_org_created",
        "paper_validation_observability_events",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_paper_validation_observability_run_id",
        "paper_validation_observability_events",
        ["run_id"],
    )
    op.create_index(
        "ix_paper_validation_sample_windows_run_id",
        "paper_validation_sample_windows",
        ["paper_validation_run_id"],
    )
    op.create_index(
        "ix_paper_validation_sample_windows_org",
        "paper_validation_sample_windows",
        ["organization_id"],
    )
    op.create_index(
        "ix_paper_validation_scheduler_configs_org",
        "paper_validation_scheduler_configs",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_paper_validation_scheduler_configs_org")
    op.drop_index("ix_paper_validation_sample_windows_org")
    op.drop_index("ix_paper_validation_sample_windows_run_id")
    op.drop_index("ix_paper_validation_observability_run_id")
    op.drop_index("ix_paper_validation_observability_org_created")
    op.drop_index("ix_paper_validation_runtime_history_run_created")
    op.drop_index("ix_paper_validation_runtime_history_org_started")
    op.drop_index("ix_paper_validation_alerts_read_at")
    op.drop_index("ix_paper_validation_alerts_dedup_key")
    op.drop_index("ix_paper_validation_alerts_org_created")
    op.drop_column("paper_validation_alerts", "dedup_key")
