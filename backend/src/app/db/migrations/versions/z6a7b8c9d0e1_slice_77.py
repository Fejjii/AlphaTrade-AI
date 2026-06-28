"""Slice 77 — setup alert review fields on paper validation alerts."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "z6a7b8c9d0e1"
down_revision = "y5z6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "paper_validation_alerts",
        sa.Column(
            "review_status",
            sa.String(length=20),
            nullable=False,
            server_default="unreviewed",
        ),
    )
    op.add_column(
        "paper_validation_alerts",
        sa.Column("review_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "paper_validation_alerts",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "paper_validation_alerts",
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_paper_validation_alerts_reviewed_by_users",
        "paper_validation_alerts",
        "users",
        ["reviewed_by"],
        ["id"],
    )
    op.create_index(
        "ix_paper_validation_alerts_org_review_status",
        "paper_validation_alerts",
        ["organization_id", "review_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_paper_validation_alerts_org_review_status")
    op.drop_constraint(
        "fk_paper_validation_alerts_reviewed_by_users",
        "paper_validation_alerts",
        type_="foreignkey",
    )
    op.drop_column("paper_validation_alerts", "reviewed_by")
    op.drop_column("paper_validation_alerts", "reviewed_at")
    op.drop_column("paper_validation_alerts", "review_notes")
    op.drop_column("paper_validation_alerts", "review_status")
