"""Slice 38 — lesson-driven strategy version metadata."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_strategy_versions",
        sa.Column("lesson_source_metadata", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_strategy_versions", "lesson_source_metadata")
