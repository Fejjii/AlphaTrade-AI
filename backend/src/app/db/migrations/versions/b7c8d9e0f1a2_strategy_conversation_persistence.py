"""strategy conversation persistence and proposal provenance

Revision ID: b7c8d9e0f1a2
Revises: e8f1c4a9b702
Create Date: 2026-09-20 17:42:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "e8f1c4a9b702"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONVERSATION_STATUS = sa.Enum(
    "ACTIVE",
    "ARCHIVED",
    name="conversationstatus",
    native_enum=False,
    length=40,
)
_MESSAGE_ROLE = sa.Enum(
    "USER",
    "ASSISTANT",
    "SYSTEM",
    name="conversationmessagerole",
    native_enum=False,
    length=40,
)
_PROPOSAL_STATUS = sa.Enum(
    "DRAFT",
    "CONFIRMED",
    "REJECTED",
    "SUPERSEDED",
    name="strategyproposalstatus",
    native_enum=False,
    length=40,
)


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("status", _CONVERSATION_STATUS, nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["user_strategies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversations_org_user_updated",
        "conversations",
        ["organization_id", "user_id", "updated_at"],
    )
    op.create_index(
        "ix_conversations_org_strategy",
        "conversations",
        ["organization_id", "strategy_id"],
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", _MESSAGE_ROLE, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(length=80), nullable=True),
        sa.Column("intent", sa.String(length=80), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_messages_conversation_created",
        "conversation_messages",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_conversation_messages_org_user",
        "conversation_messages",
        ["organization_id", "user_id"],
    )

    op.create_table(
        "strategy_conversation_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.Column("target_strategy_id", sa.Uuid(), nullable=True),
        sa.Column("parent_version_id", sa.Uuid(), nullable=True),
        sa.Column("status", _PROPOSAL_STATUS, nullable=False),
        sa.Column("proposed_structured_rules", sa.JSON(), nullable=True),
        sa.Column("proposed_pattern_spec", sa.JSON(), nullable=True),
        sa.Column("proposed_card", sa.JSON(), nullable=True),
        sa.Column("validation", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("challenge_notes", sa.JSON(), nullable=False),
        sa.Column("context_refs", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("resulting_strategy_id", sa.Uuid(), nullable=True),
        sa.Column("resulting_version_id", sa.Uuid(), nullable=True),
        sa.Column("resulting_content_hash", sa.String(length=64), nullable=True),
        sa.Column("confirmation_request_id", sa.String(length=80), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "resulting_content_hash IS NULL OR length(resulting_content_hash) = 64",
            name="ck_strategy_proposal_result_hash",
        ),
        sa.CheckConstraint(
            "content_hash IS NULL OR length(content_hash) = 64",
            name="ck_strategy_proposal_content_hash",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_message_id"], ["conversation_messages.id"]),
        sa.ForeignKeyConstraint(["target_strategy_id"], ["user_strategies.id"]),
        sa.ForeignKeyConstraint(["parent_version_id"], ["user_strategy_versions.id"]),
        sa.ForeignKeyConstraint(["resulting_strategy_id"], ["user_strategies.id"]),
        sa.ForeignKeyConstraint(["resulting_version_id"], ["user_strategy_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_strategy_proposals_org_conversation",
        "strategy_conversation_proposals",
        ["organization_id", "conversation_id", "created_at"],
    )

    op.create_table(
        "strategy_version_conversation_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["user_strategies.id"]),
        sa.ForeignKeyConstraint(["strategy_version_id"], ["user_strategy_versions.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["proposal_id"], ["strategy_conversation_proposals.id"]),
        sa.ForeignKeyConstraint(["source_message_id"], ["conversation_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy_version_id", name="uq_strategy_version_conversation_link"),
        sa.UniqueConstraint("proposal_id", name="uq_strategy_proposal_version_link"),
    )
    op.create_index(
        "ix_strategy_version_links_org_conversation",
        "strategy_version_conversation_links",
        ["organization_id", "conversation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategy_version_links_org_conversation",
        table_name="strategy_version_conversation_links",
    )
    op.drop_table("strategy_version_conversation_links")
    op.drop_index(
        "ix_strategy_proposals_org_conversation",
        table_name="strategy_conversation_proposals",
    )
    op.drop_table("strategy_conversation_proposals")
    op.drop_index("ix_conversation_messages_org_user", table_name="conversation_messages")
    op.drop_index(
        "ix_conversation_messages_conversation_created",
        table_name="conversation_messages",
    )
    op.drop_table("conversation_messages")
    op.drop_index("ix_conversations_org_strategy", table_name="conversations")
    op.drop_index("ix_conversations_org_user_updated", table_name="conversations")
    op.drop_table("conversations")
