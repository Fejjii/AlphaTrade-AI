"""Membership role enum migration for Slice 17 RBAC."""

from __future__ import annotations

from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE memberships SET role = 'owner' WHERE role IN ('owner', 'admin')")
    op.execute("UPDATE memberships SET role = 'trader' WHERE role = 'member'")


def downgrade() -> None:
    op.execute("UPDATE memberships SET role = 'member' WHERE role = 'trader'")
    op.execute("UPDATE memberships SET role = 'admin' WHERE role = 'owner' AND user_id NOT IN (SELECT user_id FROM memberships WHERE role = 'owner')")
