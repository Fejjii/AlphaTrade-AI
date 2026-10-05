"""Persist Knowledge file provenance and indexing observations on existing documents.

Revision ID: a4knowledge001
Revises: a3release002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a4knowledge001"
down_revision = "a3release002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("ingestion_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "ingestion_metadata")
