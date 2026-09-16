"""phase 1 slices 7-10 execution claim protocol

Revision ID: 4f0a2c9b71e8
Revises: 3e4e11598fa9
Create Date: 2026-09-15 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4f0a2c9b71e8"
down_revision: str | None = "3e4e11598fa9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column(
            "created_at",
            _TS,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            _TS,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_execution_account_org_identity",
        "execution_accounts",
        ["id", "organization_id"],
    )
    op.create_table(
        "execution_idempotency_bindings",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("exchange_account_id", sa.Uuid(), nullable=True),
        sa.Column("exchange_account_scope_key", sa.String(length=36), nullable=False),
        sa.Column("operation_namespace", sa.String(length=64), nullable=False),
        sa.Column("opaque_key", sa.String(length=128), nullable=False),
        sa.Column("canonical_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("authorization_id", sa.Uuid(), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=True),
        sa.Column("receipt_id", sa.Uuid(), nullable=True),
        sa.Column(
            "outcome",
            sa.Enum("ALLOW", "BLOCKED", name="executioncommandoutcome", native_enum=False, length=40),
            nullable=True,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "length(canonical_payload_hash) = 64",
            name="ck_execution_idempotency_payload_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "organization_id", "user_id"],
            [
                "execution_accounts.id",
                "execution_accounts.organization_id",
                "execution_accounts.user_id",
            ],
            name="fk_execution_idempotency_account_tenant",
        ),
        sa.ForeignKeyConstraint(["authorization_id"], ["approval_authorizations.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["trade_plan_revisions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "opaque_key",
            name="uq_execution_idempotency_binding",
        ),
    )

    op.create_table(
        "execution_commands",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("exchange_account_id", sa.Uuid(), nullable=True),
        sa.Column(
            "operation",
            sa.Enum("SUBMIT_ENTRY", name="planoperation", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("operation_namespace", sa.String(length=64), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("authorization_id", sa.Uuid(), nullable=False),
        sa.Column("plan_content_hash", sa.String(length=64), nullable=False),
        sa.Column("canonical_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("opaque_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum("ALLOW", "BLOCKED", name="executioncommandoutcome", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("blocked_reason_code", sa.String(length=80), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "length(canonical_payload_hash) = 64",
            name="ck_execution_command_payload_hash_length",
        ),
        sa.CheckConstraint("length(plan_content_hash) = 64", name="ck_execution_command_plan_hash"),
        sa.CheckConstraint(
            "operation_namespace = 'alphatrade/submit-entry/v1'",
            name="ck_execution_command_entry_namespace",
        ),
        sa.CheckConstraint("operation = 'SUBMIT_ENTRY'", name="ck_execution_command_submit_entry"),
        sa.ForeignKeyConstraint(["authorization_id"], ["approval_authorizations.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["revision_id", "plan_id", "organization_id", "user_id", "account_id"],
            [
                "trade_plan_revisions.id",
                "trade_plan_revisions.plan_id",
                "trade_plan_revisions.organization_id",
                "trade_plan_revisions.user_id",
                "trade_plan_revisions.account_id",
            ],
            name="fk_execution_command_revision_binding",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_execution_commands_org_account",
        "execution_commands",
        ["organization_id", "account_id"],
    )

    op.create_table(
        "execution_receipts",
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column(
            "operation",
            sa.Enum("SUBMIT_ENTRY", name="planoperation", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("authorization_id", sa.Uuid(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["authorization_id"], ["approval_authorizations.id"]),
        sa.ForeignKeyConstraint(
            ["command_id"],
            ["execution_commands.id"],
            name="fk_execution_receipt_command",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("command_id", name="uq_execution_receipt_command"),
    )

    op.create_table(
        "plan_entry_execution_claims",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("exchange_account_id", sa.Uuid(), nullable=True),
        sa.Column("exchange_account_scope_key", sa.String(length=36), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column(
            "operation",
            sa.Enum("SUBMIT_ENTRY", name="planoperation", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("operation = 'SUBMIT_ENTRY'", name="ck_plan_entry_claim_submit_entry"),
        sa.ForeignKeyConstraint(
            ["command_id"],
            ["execution_commands.id"],
            name="fk_plan_entry_claim_command",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["execution_receipts.id"],
            name="fk_plan_entry_claim_receipt",
        ),
        sa.ForeignKeyConstraint(["revision_id"], ["trade_plan_revisions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("command_id", name="uq_plan_entry_execution_claim_command"),
        sa.UniqueConstraint(
            "organization_id",
            "account_id",
            "exchange_account_scope_key",
            "revision_id",
            "operation",
            name="uq_plan_entry_execution_claim",
        ),
    )

    op.create_table(
        "account_safety_epochs",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("epoch", sa.BigInteger(), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("last_reason_code", sa.String(length=80), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("epoch >= 1", name="ck_account_safety_epoch_positive"),
        sa.ForeignKeyConstraint(
            ["account_id", "organization_id"],
            ["execution_accounts.id", "execution_accounts.organization_id"],
            name="fk_account_safety_epoch_account",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "account_id", name="uq_account_safety_epoch"),
    )

    op.create_table(
        "account_risk_accounting_states",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("reserved_notional", sa.Numeric(20, 8), nullable=False),
        sa.Column("reserved_daily_loss", sa.Numeric(20, 8), nullable=False),
        sa.Column("reserved_trade_slots", sa.Integer(), nullable=False),
        sa.Column("actual_notional", sa.Numeric(20, 8), nullable=False),
        sa.Column("actual_daily_loss", sa.Numeric(20, 8), nullable=False),
        sa.Column("actual_trade_count", sa.Integer(), nullable=False),
        sa.Column("symbol_reserved", sa.JSON(), nullable=False),
        sa.Column("symbol_actual", sa.JSON(), nullable=False),
        sa.Column("max_notional", sa.Numeric(20, 8), nullable=False),
        sa.Column("max_daily_loss", sa.Numeric(20, 8), nullable=False),
        sa.Column("max_trade_slots", sa.Integer(), nullable=False),
        sa.Column("max_symbol_notional", sa.Numeric(20, 8), nullable=False),
        sa.Column("daily_locked", sa.Boolean(), nullable=False),
        sa.Column("exposure_unit", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("actual_notional >= 0", name="ck_account_risk_actual_notional"),
        sa.CheckConstraint("max_notional >= 0", name="ck_account_risk_max_notional"),
        sa.CheckConstraint("reserved_notional >= 0", name="ck_account_risk_reserved_notional"),
        sa.CheckConstraint("reserved_trade_slots >= 0", name="ck_account_risk_reserved_slots"),
        sa.ForeignKeyConstraint(
            ["account_id", "organization_id"],
            ["execution_accounts.id", "execution_accounts.organization_id"],
            name="fk_account_risk_accounting_account",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "account_id",
            name="uq_account_risk_accounting_state",
        ),
    )

    receipt_state = sa.Enum(
        "BLOCKED",
        "SUBMITTING",
        "BLOCKED_BEFORE_DISPATCH",
        "ACKNOWLEDGED",
        "PARTIALLY_FILLED",
        "REJECTED",
        "EXPIRED",
        "CANCELLED",
        "PARTIALLY_FILLED_CANCELLED",
        "RECONCILIATION_REQUIRED",
        "ABSENCE_PENDING",
        "ABSENCE_PROVEN",
        "RESUBMIT_AUTHORIZED",
        "OPERATOR_HOLD",
        name="executionreceiptstate",
        native_enum=False,
        length=40,
    )
    recon_status = sa.Enum(
        "NOT_REQUIRED",
        "REQUIRED",
        "IN_PROGRESS",
        "RESOLVED",
        "OPERATOR_HOLD",
        name="executionreconciliationstatus",
        native_enum=False,
        length=40,
    )

    op.create_table(
        "execution_transitions",
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("prior_state", sa.String(length=40), nullable=True),
        sa.Column("new_state", receipt_state, nullable=False),
        sa.Column("source_fact", sa.String(length=80), nullable=False),
        sa.Column("source_identity", sa.String(length=128), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=True),
        sa.Column("quantity_unit", sa.String(length=32), nullable=True),
        sa.Column("occurred_at", _TS, nullable=False),
        sa.Column("observed_at", _TS, nullable=False),
        sa.Column("recorded_at", _TS, nullable=False),
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "length(content_hash) = 64",
            name="ck_execution_transition_hash_length",
        ),
        sa.CheckConstraint("sequence >= 1", name="ck_execution_transition_sequence"),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["execution_receipts.id"],
            name="fk_execution_transition_receipt",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_id", "sequence", name="uq_execution_transition_sequence"),
    )
    op.create_index(
        "ix_execution_transitions_receipt_seq",
        "execution_transitions",
        ["receipt_id", "sequence"],
    )

    op.create_table(
        "execution_projections",
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", receipt_state, nullable=False),
        sa.Column("filled_quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("remaining_quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("quantity_unit", sa.String(length=32), nullable=False),
        sa.Column("weighted_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("fees", sa.Numeric(20, 8), nullable=False),
        sa.Column("funding", sa.Numeric(20, 8), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=True),
        sa.Column("reconciliation_status", recon_status, nullable=False),
        sa.Column("event_watermark", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("event_watermark >= 0", name="ck_execution_projection_watermark"),
        sa.CheckConstraint("version >= 1", name="ck_execution_projection_version"),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["execution_receipts.id"],
            name="fk_execution_projection_receipt",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_id", name="uq_execution_projection_receipt"),
    )

    op.create_table(
        "risk_reservations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("instrument", sa.String(length=120), nullable=False),
        sa.Column("risk_policy_version", sa.String(length=64), nullable=False),
        sa.Column("risk_snapshot_version", sa.String(length=64), nullable=False),
        sa.Column("pending_order_exposure", sa.Numeric(20, 8), nullable=False),
        sa.Column("submitting_or_ambiguous_exposure", sa.Numeric(20, 8), nullable=False),
        sa.Column("open_order_notional", sa.Numeric(20, 8), nullable=False),
        sa.Column("daily_trade_allocation", sa.Integer(), nullable=False),
        sa.Column("daily_loss_allocation", sa.Numeric(20, 8), nullable=False),
        sa.Column("total_exposure", sa.Numeric(20, 8), nullable=False),
        sa.Column("symbol_exposure", sa.Numeric(20, 8), nullable=False),
        sa.Column("remaining_reserved_notional", sa.Numeric(20, 8), nullable=False),
        sa.Column("exposure_unit", sa.String(length=32), nullable=False),
        sa.Column("safety_epoch", sa.BigInteger(), nullable=False),
        sa.Column(
            "release_state",
            sa.Enum(
                "CHARGED",
                "PARTIALLY_RELEASED",
                "RELEASED",
                name="riskreservationreleasestate",
                native_enum=False,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column(
            "release_reason",
            sa.Enum(
                "UNUSED_REMAINDER_AFTER_REJECTION",
                "UNUSED_REMAINDER_AFTER_CANCELLATION",
                "UNUSED_REMAINDER_AFTER_EXPIRY",
                "UNUSED_REMAINDER_AFTER_ABSENCE",
                "UNUSED_REMAINDER_AFTER_PROVEN_UNSENT",
                "FILL_CONVERSION",
                name="riskreservationreleasereason",
                native_enum=False,
                length=40,
            ),
            nullable=True,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("pending_order_exposure >= 0", name="ck_risk_reservation_pending"),
        sa.CheckConstraint(
            "remaining_reserved_notional >= 0",
            name="ck_risk_reservation_remaining",
        ),
        sa.ForeignKeyConstraint(
            ["command_id"],
            ["execution_commands.id"],
            name="fk_risk_reservation_command",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["plan_revision_id"],
            ["trade_plan_revisions.id"],
            name="fk_risk_reservation_revision",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["execution_receipts.id"],
            name="fk_risk_reservation_receipt",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("command_id", name="uq_risk_reservation_command"),
        sa.UniqueConstraint("receipt_id", name="uq_risk_reservation_receipt"),
    )

    op.create_table(
        "venue_submit_effects",
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("client_order_id", sa.String(length=64), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "CREATED",
                "LEASED",
                "DISPATCH_AUTHORIZED",
                "PROVEN_UNSENT",
                "SEND_ATTEMPTED",
                "SEND_AMBIGUOUS",
                "RECONCILING",
                name="venuesubmiteffectstate",
                native_enum=False,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("lease_owner", sa.String(length=80), nullable=True),
        sa.Column("lease_expires_at", _TS, nullable=True),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("dispatch_authorized_at", _TS, nullable=True),
        sa.Column("dispatch_safety_epoch", sa.BigInteger(), nullable=True),
        sa.Column("dispatch_fencing_token", sa.Integer(), nullable=True),
        sa.Column("dispatch_attempt", sa.Integer(), nullable=True),
        sa.Column("safety_epoch", sa.BigInteger(), nullable=False),
        sa.Column("uncertainty", sa.Boolean(), nullable=False),
        sa.Column("reconciliation_disposition", sa.String(length=80), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("attempt >= 0", name="ck_venue_submit_effect_attempt"),
        sa.CheckConstraint("fencing_token >= 0", name="ck_venue_submit_effect_fence"),
        sa.ForeignKeyConstraint(
            ["command_id"],
            ["execution_commands.id"],
            name="fk_venue_submit_effect_command",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["execution_receipts.id"],
            name="fk_venue_submit_effect_receipt",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_order_id", name="uq_venue_submit_effect_client_order_id"),
        sa.UniqueConstraint("command_id", name="uq_venue_submit_effect_command"),
        sa.UniqueConstraint("receipt_id", name="uq_venue_submit_effect_receipt"),
    )


def downgrade() -> None:
    op.drop_table("venue_submit_effects")
    op.drop_table("risk_reservations")
    op.drop_table("execution_projections")
    op.drop_index("ix_execution_transitions_receipt_seq", table_name="execution_transitions")
    op.drop_table("execution_transitions")
    op.drop_table("account_risk_accounting_states")
    op.drop_table("account_safety_epochs")
    op.drop_table("plan_entry_execution_claims")
    op.drop_table("execution_receipts")
    op.drop_index("ix_execution_commands_org_account", table_name="execution_commands")
    op.drop_table("execution_commands")
    op.drop_table("execution_idempotency_bindings")
    op.drop_constraint(
        "uq_execution_account_org_identity",
        "execution_accounts",
        type_="unique",
    )
