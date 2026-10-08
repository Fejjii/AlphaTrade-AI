"""Audited manual demo lifecycle recovery; preserve all historical attempts.

Revision ID: a7manualrecovery001
Revises: a6manualdemo001
"""

import sqlalchemy as sa
from alembic import op

revision = "a7manualrecovery001"
down_revision = "a6manualdemo001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manual_demo_lifecycle_resolutions",
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
        sa.Column("audit_event_id", sa.Uuid(), sa.ForeignKey("audit_logs.id"), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_notional", sa.Numeric(20, 8), nullable=False),
        sa.UniqueConstraint("command_id", name="uq_manual_demo_resolution_command"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_manual_demo_resolution_hash"),
        sa.CheckConstraint("released_notional >= 0", name="ck_manual_demo_resolution_release"),
        sa.CheckConstraint(
            "reason IN ('verified_exit', 'terminal_unfilled', 'proven_unsent')",
            name="ck_manual_demo_resolution_reason",
        ),
    )
    op.create_index(
        "ix_manual_demo_resolution_scope",
        "manual_demo_lifecycle_resolutions",
        ["organization_id", "account_id"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE TRIGGER trg_manual_demo_lifecycle_resolutions_immutable BEFORE UPDATE OR DELETE ON manual_demo_lifecycle_resolutions FOR EACH ROW EXECUTE PROCEDURE alphatrade_forbid_historical_mutation()"
        )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM manual_demo_lifecycle_resolutions LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Manual demo recovery history exists; use forward recovery.")
    op.drop_table("manual_demo_lifecycle_resolutions")
