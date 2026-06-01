"""RAG slice 12 — document and chunk metadata extensions.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-01

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "documents",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_unique_constraint(
        "uq_document_org_source_hash",
        "documents",
        ["organization_id", "source_hash"],
    )

    op.add_column("chunks", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.add_column("chunks", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.add_column("chunks", sa.Column("text_hash", sa.String(length=64), nullable=True))
    op.create_foreign_key(
        op.f("fk_chunks_organization_id_organizations"),
        "chunks",
        "organizations",
        ["organization_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_chunks_user_id_users"),
        "chunks",
        "users",
        ["user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_chunks_user_id_users"), "chunks", type_="foreignkey")
    op.drop_constraint(op.f("fk_chunks_organization_id_organizations"), "chunks", type_="foreignkey")
    op.drop_column("chunks", "text_hash")
    op.drop_column("chunks", "user_id")
    op.drop_column("chunks", "organization_id")

    op.drop_constraint("uq_document_org_source_hash", "documents", type_="unique")
    op.drop_column("documents", "version")
    op.drop_column("documents", "source_hash")
