"""Slice 37 — lesson review workflow, extended lesson candidates."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lesson_candidates", sa.Column("source_type", sa.String(length=40), nullable=True))
    op.add_column("lesson_candidates", sa.Column("source_id", sa.Uuid(), nullable=True))
    op.add_column("lesson_candidates", sa.Column("related_strategy_id", sa.Uuid(), nullable=True))
    op.add_column(
        "lesson_candidates",
        sa.Column("related_journal_entry_id", sa.Uuid(), nullable=True),
    )
    op.add_column("lesson_candidates", sa.Column("lesson_text", sa.Text(), nullable=True))
    op.add_column("lesson_candidates", sa.Column("mistake_type", sa.String(length=60), nullable=True))
    op.add_column("lesson_candidates", sa.Column("severity", sa.String(length=20), nullable=True))
    op.add_column("lesson_candidates", sa.Column("confidence", sa.Numeric(5, 4), nullable=True))
    op.add_column("lesson_candidates", sa.Column("proposed_rule_update", sa.JSON(), nullable=True))
    op.add_column("lesson_candidates", sa.Column("accepted_rule_update", sa.JSON(), nullable=True))
    op.add_column("lesson_candidates", sa.Column("reviewer_notes", sa.Text(), nullable=True))
    op.add_column(
        "lesson_candidates",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("lesson_candidates", sa.Column("analysis_metadata", sa.JSON(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE lesson_candidates SET
                lesson_text = summary,
                mistake_type = category,
                related_journal_entry_id = journal_entry_id,
                source_type = 'journal',
                source_id = journal_entry_id,
                severity = 'medium',
                confidence = 0.5,
                status = CASE
                    WHEN status = 'lesson_candidate' THEN 'pending_review'
                    WHEN status = 'needs_review' THEN 'pending_review'
                    WHEN status = 'accepted_lesson' THEN 'accepted'
                    WHEN status = 'rejected_lesson' THEN 'rejected'
                    ELSE status
                END
            """
        )
    )

    op.alter_column("lesson_candidates", "lesson_text", nullable=False)
    op.alter_column("lesson_candidates", "mistake_type", nullable=False)
    op.alter_column("lesson_candidates", "source_type", nullable=False, server_default="journal")
    op.alter_column("lesson_candidates", "severity", nullable=False, server_default="medium")

    op.drop_column("lesson_candidates", "category")
    op.drop_column("lesson_candidates", "summary")

    op.create_foreign_key(
        "fk_lesson_candidates_related_strategy",
        "lesson_candidates",
        "user_strategies",
        ["related_strategy_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_lesson_candidates_related_journal",
        "lesson_candidates",
        "journals",
        ["related_journal_entry_id"],
        ["id"],
    )


def downgrade() -> None:
    op.add_column("lesson_candidates", sa.Column("category", sa.String(length=60), nullable=True))
    op.add_column("lesson_candidates", sa.Column("summary", sa.Text(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE lesson_candidates SET
                category = mistake_type,
                summary = lesson_text,
                status = CASE
                    WHEN status = 'pending_review' THEN 'lesson_candidate'
                    WHEN status = 'accepted' THEN 'accepted_lesson'
                    WHEN status = 'rejected' THEN 'rejected_lesson'
                    ELSE status
                END
            """
        )
    )
    op.drop_constraint("fk_lesson_candidates_related_journal", "lesson_candidates", type_="foreignkey")
    op.drop_constraint(
        "fk_lesson_candidates_related_strategy", "lesson_candidates", type_="foreignkey"
    )
    for col in (
        "analysis_metadata",
        "reviewed_at",
        "reviewer_notes",
        "accepted_rule_update",
        "proposed_rule_update",
        "confidence",
        "severity",
        "mistake_type",
        "lesson_text",
        "related_journal_entry_id",
        "related_strategy_id",
        "source_id",
        "source_type",
    ):
        op.drop_column("lesson_candidates", col)
