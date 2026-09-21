"""durable paper Telegram notification/thread identity

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-09-21 21:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9e0f1a2b3c4"
down_revision: str | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_paper_notifications",
        sa.Column("intent_id", sa.Uuid(), nullable=False),
        sa.Column("identity_hash", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("telegram_revision_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("watcher_lineage_id", sa.Uuid(), nullable=True),
        sa.Column("watcher_reason_code", sa.String(length=80), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("intent_id"),
        sa.UniqueConstraint("identity_hash", name="uq_tg_paper_notify_identity"),
        sa.UniqueConstraint("organization_id", "intent_id", name="uq_tg_paper_notify_org_intent"),
        sa.CheckConstraint("length(identity_hash) = 64", name="ck_tg_paper_notify_identity_len"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_tg_paper_notify_content_len"),
    )
    op.create_table(
        "telegram_paper_threads",
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("binding_id", sa.Uuid(), nullable=False),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("chat_id", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("notification_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("thread_id"),
    )
    op.create_index(
        "uq_tg_paper_thread_scope_resource",
        "telegram_paper_threads",
        ["organization_id", "binding_id", "resource_type", "resource_id"],
        unique=True,
        postgresql_where=sa.text("resource_id IS NOT NULL"),
    )
    op.create_index(
        "uq_tg_paper_thread_scope_null_resource",
        "telegram_paper_threads",
        ["organization_id", "binding_id", "resource_type"],
        unique=True,
        postgresql_where=sa.text("resource_id IS NULL"),
    )
    op.create_table(
        "telegram_paper_messages",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["telegram_paper_threads.thread_id"]),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_table(
        "telegram_paper_confirmations",
        sa.Column("confirmation_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("presented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["thread_id"], ["telegram_paper_threads.thread_id"]),
        sa.PrimaryKeyConstraint("confirmation_id"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_tg_paper_confirm_content_len"),
        sa.CheckConstraint("length(payload_hash) = 64", name="ck_tg_paper_confirm_payload_len"),
    )


def downgrade() -> None:
    op.drop_table("telegram_paper_confirmations")
    op.drop_table("telegram_paper_messages")
    op.drop_index(
        "uq_tg_paper_thread_scope_null_resource", table_name="telegram_paper_threads"
    )
    op.drop_index("uq_tg_paper_thread_scope_resource", table_name="telegram_paper_threads")
    op.drop_table("telegram_paper_threads")
    op.drop_table("telegram_paper_notifications")
