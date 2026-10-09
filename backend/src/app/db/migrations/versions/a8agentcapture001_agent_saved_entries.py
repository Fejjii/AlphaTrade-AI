"""Add isolated Agent note/draft storage and durable capture deduplication."""

from typing import Any

from alembic import op
import sqlalchemy as sa

revision = "a8agentcapture001"
down_revision = "a7manualrecovery001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables: list[tuple[str, list[sa.Column[Any] | sa.UniqueConstraint]]] = [
        (
            "agent_saved_entries",
            [
                sa.Column(
                    "conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id"), nullable=False
                ),
                sa.Column("category", sa.String(30), nullable=False),
                sa.Column("title", sa.String(160), nullable=False),
                sa.Column("summary", sa.Text(), nullable=False),
                sa.Column("original_text", sa.Text(), nullable=False),
                sa.Column("sources", sa.JSON(), nullable=False),
                sa.Column("draft", sa.JSON(), nullable=True),
                sa.Column("revision", sa.Integer(), nullable=False),
                sa.Column("history", sa.JSON(), nullable=False),
                sa.Column("undone", sa.Boolean(), nullable=False),
            ],
        ),
        (
            "agent_capture_sources",
            [
                sa.Column("source_hash", sa.String(64), nullable=False),
                sa.Column("entry_ids", sa.JSON(), nullable=False),
                sa.UniqueConstraint(
                    "organization_id", "user_id", "source_hash", name="uq_agent_capture_source"
                ),
            ],
        ),
    ]
    for table, columns in tables:
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False
            ),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            *columns,
        )
    op.create_index(
        "ix_agent_saved_scope", "agent_saved_entries", ["organization_id", "user_id", "category"]
    )


def downgrade() -> None:
    op.drop_index("ix_agent_saved_scope", table_name="agent_saved_entries")
    op.drop_table("agent_capture_sources")
    op.drop_table("agent_saved_entries")
