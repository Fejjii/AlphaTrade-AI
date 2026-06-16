"""Slice 36 — structured rules, lesson candidates."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_strategy_versions",
        sa.Column("structured_rules", sa.JSON(), nullable=True),
    )
    op.create_table(
        "lesson_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("journal_entry_id", sa.Uuid(), nullable=True),
        sa.Column("trade_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="lesson_candidate"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journals.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("lesson_candidates")
    op.drop_column("user_strategy_versions", "structured_rules")
