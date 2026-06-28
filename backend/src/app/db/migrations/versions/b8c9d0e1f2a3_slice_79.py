"""Slice 79 — paper validation draft prep workflow fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("paper_validation_drafts", sa.Column("thesis", sa.Text(), nullable=True))
    op.add_column("paper_validation_drafts", sa.Column("entry_criteria", sa.Text(), nullable=True))
    op.add_column(
        "paper_validation_drafts", sa.Column("invalidation_criteria", sa.Text(), nullable=True)
    )
    op.add_column("paper_validation_drafts", sa.Column("risk_notes", sa.Text(), nullable=True))
    op.add_column(
        "paper_validation_drafts",
        sa.Column("checklist_status", sa.JSON(), nullable=True),
    )
    op.add_column(
        "paper_validation_drafts",
        sa.Column("prep_status", sa.String(length=32), nullable=False, server_default="draft"),
    )


def downgrade() -> None:
    op.drop_column("paper_validation_drafts", "prep_status")
    op.drop_column("paper_validation_drafts", "checklist_status")
    op.drop_column("paper_validation_drafts", "risk_notes")
    op.drop_column("paper_validation_drafts", "invalidation_criteria")
    op.drop_column("paper_validation_drafts", "entry_criteria")
    op.drop_column("paper_validation_drafts", "thesis")
