"""Immutable verified demo lifecycle resolutions; no execution activation.

Revision ID: a5demolifecycle001
Revises: a4knowledge001
"""

import sqlalchemy as sa
from alembic import op

from app.db.historical_immutability import historical_immutability_demo_install_statements

revision = "a5demolifecycle001"
down_revision = "a4knowledge001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "governed_demo_lifecycle_resolutions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("execution_accounts.id"), nullable=False),
        sa.Column("command_id", sa.Uuid(), sa.ForeignKey("execution_commands.id"), nullable=False),
        sa.Column(
            "revision_id", sa.Uuid(), sa.ForeignKey("trade_plan_revisions.id"), nullable=False
        ),
        sa.Column(
            "journal_close_event_id",
            sa.Uuid(),
            sa.ForeignKey("journal_lifecycle_events.id"),
            nullable=False,
        ),
        sa.Column("audit_event_id", sa.Uuid(), sa.ForeignKey("audit_logs.id"), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_notional", sa.Numeric(20, 8), nullable=False),
        sa.Column("risk_accounting_version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("command_id", name="uq_demo_lifecycle_command"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_demo_lifecycle_hash"),
        sa.CheckConstraint("released_notional >= 0", name="ck_demo_lifecycle_release"),
    )
    op.create_index(
        "ix_demo_lifecycle_org_account",
        "governed_demo_lifecycle_resolutions",
        ["organization_id", "account_id"],
    )
    if op.get_bind().dialect.name == "postgresql":
        for statement in historical_immutability_demo_install_statements():
            op.execute(statement)


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM governed_demo_lifecycle_resolutions LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot remove preserved demo lifecycle history; use forward recovery.")
    op.drop_table("governed_demo_lifecycle_resolutions")
