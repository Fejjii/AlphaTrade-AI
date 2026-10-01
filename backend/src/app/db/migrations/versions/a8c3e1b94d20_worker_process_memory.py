"""worker process memory on controlled runtime status

Revision ID: a8c3e1b94d20
Revises: f1a2b3c4d5e6
Create Date: 2026-09-28 07:40:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c3e1b94d20"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "controlled_runtime_status",
        sa.Column("process_rss_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "controlled_runtime_status",
        sa.Column("process_rss_peak_bytes", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("controlled_runtime_status", "process_rss_peak_bytes")
    op.drop_column("controlled_runtime_status", "process_rss_bytes")
