"""watcher telegram postgres persistence

Revision ID: 3ec264f9aaa8
Revises: a0c1d2e3f4b5
Create Date: 2026-09-17 08:14:41.979634
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "3ec264f9aaa8"
down_revision: str | None = "a0c1d2e3f4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_security_action_nonces",
        sa.Column("nonce_id", sa.Uuid(), nullable=False),
        sa.Column("nonce_hash", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("telegram_user_id", sa.String(length=64), nullable=False),
        sa.Column("chat_id", sa.String(length=64), nullable=False),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("binding_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_by_receipt_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "length(nonce_hash) = 64",
            name=op.f("ck_telegram_security_action_nonces_tgsec_nonce_hash_len"),
        ),
        sa.CheckConstraint(
            "length(payload_hash) = 64",
            name=op.f("ck_telegram_security_action_nonces_tgsec_nonce_payload_hash_len"),
        ),
        sa.PrimaryKeyConstraint("nonce_id", name=op.f("pk_telegram_security_action_nonces")),
        sa.UniqueConstraint("nonce_hash", name="uq_tgsec_nonces_hash"),
        sa.UniqueConstraint(
            "organization_id", "nonce_hash", "payload_hash", name="uq_tgsec_nonces_org_hash_payload"
        ),
        sa.UniqueConstraint("organization_id", "nonce_hash", name="uq_tgsec_nonces_org_hash"),
        sa.UniqueConstraint("organization_id", "nonce_id", name="uq_tgsec_nonces_org_id"),
    )
    op.create_table(
        "telegram_security_action_receipts",
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("callback_query_id", sa.String(length=128), nullable=True),
        sa.Column("message_id", sa.String(length=64), nullable=True),
        sa.Column("telegram_user_id", sa.String(length=64), nullable=False),
        sa.Column("chat_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("nonce_hash", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column("replay_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("authorization_intent_id", sa.Uuid(), nullable=True),
        sa.Column("binding_id", sa.Uuid(), nullable=True),
        sa.Column("effect_kind", sa.String(length=64), nullable=False),
        sa.Column("transitions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(replay_fingerprint) = 64",
            name=op.f("ck_telegram_security_action_receipts_tgsec_receipt_fp_len"),
        ),
        sa.CheckConstraint(
            "update_id >= 0",
            name=op.f("ck_telegram_security_action_receipts_tgsec_receipt_update_id_min"),
        ),
        sa.PrimaryKeyConstraint("receipt_id", name=op.f("pk_telegram_security_action_receipts")),
        sa.UniqueConstraint("bot_id", "update_id", name="uq_tgsec_receipts_bot_update"),
    )
    op.create_index(
        "uq_tgsec_receipts_bot_callback",
        "telegram_security_action_receipts",
        ["bot_id", "callback_query_id"],
        unique=True,
        postgresql_where=sa.text("callback_query_id IS NOT NULL"),
    )
    op.create_table(
        "telegram_security_audit_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_telegram_security_audit_events")),
    )
    op.create_index(
        "ix_tgsec_audit_org_at",
        "telegram_security_audit_events",
        ["organization_id", "at"],
        unique=False,
    )
    op.create_table(
        "telegram_security_bindings",
        sa.Column("binding_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("telegram_user_id", sa.String(length=64), nullable=False),
        sa.Column("chat_id", sa.String(length=64), nullable=False),
        sa.Column("chat_type", sa.String(length=32), nullable=False),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("allowed_actions", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("binding_id", name=op.f("pk_telegram_security_bindings")),
        sa.UniqueConstraint("organization_id", "binding_id", name="uq_tgsec_bindings_org_id"),
    )
    op.create_index(
        "uq_tgsec_bindings_active_bot_chat",
        "telegram_security_bindings",
        ["bot_id", "chat_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "uq_tgsec_bindings_active_bot_tg_user",
        "telegram_security_bindings",
        ["bot_id", "telegram_user_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "uq_tgsec_bindings_active_org_user",
        "telegram_security_bindings",
        ["organization_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_table(
        "telegram_security_enrollment_challenges",
        sa.Column("challenge_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("binding_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "length(token_hash) = 64",
            name=op.f("ck_telegram_security_enrollment_challenges_tgsec_challenge_hash_len"),
        ),
        sa.PrimaryKeyConstraint(
            "challenge_id", name=op.f("pk_telegram_security_enrollment_challenges")
        ),
        sa.UniqueConstraint("organization_id", "challenge_id", name="uq_tgsec_challenges_org_id"),
        sa.UniqueConstraint(
            "organization_id", "token_hash", name="uq_tgsec_challenges_org_token_hash"
        ),
        sa.UniqueConstraint("token_hash", name="uq_tgsec_challenges_token_hash"),
    )
    op.create_index(
        "ix_tgsec_challenges_binding_id",
        "telegram_security_enrollment_challenges",
        ["binding_id"],
        unique=False,
    )
    op.create_index(
        "ix_tgsec_challenges_org_user_bot_state",
        "telegram_security_enrollment_challenges",
        ["organization_id", "user_id", "bot_id", "state"],
        unique=False,
    )
    op.create_table(
        "telegram_security_outbox",
        sa.Column("outbox_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("binding_id", sa.Uuid(), nullable=True),
        sa.Column("bot_id", sa.String(length=64), nullable=False),
        sa.Column("chat_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("text", sa.String(length=4096), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transport_message_id", sa.String(length=128), nullable=True),
        sa.Column("last_error", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempt >= 0", name=op.f("ck_telegram_security_outbox_tgsec_outbox_attempt_min")
        ),
        sa.PrimaryKeyConstraint("outbox_id", name=op.f("pk_telegram_security_outbox")),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_tgsec_outbox_org_idempotency"
        ),
        sa.UniqueConstraint("organization_id", "outbox_id", name="uq_tgsec_outbox_org_id"),
    )
    op.create_index(
        "ix_tgsec_outbox_claim",
        "telegram_security_outbox",
        ["state", "lease_until", "created_at"],
        unique=False,
    )
    op.create_table(
        "watcher_health_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("scan_scope", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_epoch", sa.Integer(), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_beat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seconds_since_beat", sa.Float(), nullable=True),
        sa.Column("last_attempt_status", sa.String(length=32), nullable=True),
        sa.Column("last_lineage_id", sa.Uuid(), nullable=True),
        sa.Column("reason_code", sa.String(length=128), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watcher_health_snapshots")),
        sa.UniqueConstraint(
            "organization_id", "scan_scope", name="uq_watcher_health_snapshots_org_scope"
        ),
    )
    op.create_table(
        "watcher_heartbeats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("scan_scope", sa.String(length=200), nullable=False),
        sa.Column("owner_id", sa.String(length=128), nullable=True),
        sa.Column("lease_epoch", sa.Integer(), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("last_beat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detail", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watcher_heartbeats")),
        sa.UniqueConstraint(
            "organization_id", "scan_scope", name="uq_watcher_heartbeats_org_scope"
        ),
    )
    op.create_table(
        "watcher_observability_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lineage_id", sa.Uuid(), nullable=True),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("scan_scope", sa.String(length=200), nullable=True),
        sa.Column("fencing_token", sa.Integer(), nullable=True),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_watcher_observability_events")),
    )
    op.create_index(
        "ix_watcher_observability_events_org_scope",
        "watcher_observability_events",
        ["organization_id", "scan_scope"],
        unique=False,
    )
    op.create_table(
        "watcher_policy_versions",
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("watchlist_item_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("timeframe", sa.String(length=32), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=True),
        sa.Column("setup_definition_id", sa.Uuid(), nullable=True),
        sa.Column("fusion_policy_version", sa.String(length=128), nullable=True),
        sa.Column("alert_threshold", sa.String(length=128), nullable=True),
        sa.Column("delivery_policy_id", sa.Uuid(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "length(content_hash) = 64",
            name=op.f("ck_watcher_policy_versions_watcher_policy_hash_len"),
        ),
        sa.CheckConstraint(
            "version >= 1", name=op.f("ck_watcher_policy_versions_watcher_policy_version_min")
        ),
        sa.PrimaryKeyConstraint("policy_id", "version", name=op.f("pk_watcher_policy_versions")),
        sa.UniqueConstraint(
            "organization_id",
            "policy_id",
            "version",
            name="uq_watcher_policy_versions_org_policy_version",
        ),
        sa.UniqueConstraint(
            "policy_id", "version", name="uq_watcher_policy_versions_policy_version"
        ),
    )
    op.create_index(
        op.f("ix_watcher_policy_versions_organization_id"),
        "watcher_policy_versions",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "watcher_scan_lineages",
        sa.Column("lineage_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=True),
        sa.Column("scan_scope", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("policy_content_hash", sa.String(length=64), nullable=False),
        sa.Column("trigger_created_by", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminal_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("terminal_status", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("lineage_id", name=op.f("pk_watcher_scan_lineages")),
        sa.UniqueConstraint(
            "organization_id", "lineage_id", name="uq_watcher_scan_lineages_org_lineage"
        ),
    )
    op.create_index(
        "ix_watcher_scan_lineages_org_scope",
        "watcher_scan_lineages",
        ["organization_id", "scan_scope"],
        unique=False,
    )
    op.create_table(
        "watcher_worker_leases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("scan_scope", sa.String(length=200), nullable=False),
        sa.Column("owner_id", sa.String(length=128), nullable=True),
        sa.Column("lease_epoch", sa.Integer(), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("renewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "fencing_token = lease_epoch",
            name=op.f("ck_watcher_worker_leases_watcher_lease_fence_equals_epoch"),
        ),
        sa.CheckConstraint(
            "fencing_token >= 0", name=op.f("ck_watcher_worker_leases_watcher_lease_fence_min")
        ),
        sa.CheckConstraint(
            "lease_epoch >= 0", name=op.f("ck_watcher_worker_leases_watcher_lease_epoch_min")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watcher_worker_leases")),
        sa.UniqueConstraint(
            "organization_id", "scan_scope", name="uq_watcher_worker_leases_org_scope"
        ),
    )
    op.create_table(
        "telegram_security_authorization_intents",
        sa.Column("intent_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("executes", sa.Boolean(), nullable=False),
        sa.Column("execution_attempted", sa.Boolean(), nullable=False),
        sa.Column("execution_entry_path", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "action = 'APPROVE'",
            name=op.f("ck_telegram_security_authorization_intents_tgsec_intent_approve_only"),
        ),
        sa.CheckConstraint(
            "executes IS FALSE",
            name=op.f("ck_telegram_security_authorization_intents_tgsec_intent_never_executes"),
        ),
        sa.CheckConstraint(
            "execution_attempted IS FALSE",
            name=op.f("ck_telegram_security_authorization_intents_tgsec_intent_never_attempted"),
        ),
        sa.CheckConstraint(
            "execution_entry_path IS NULL",
            name=op.f(
                "ck_telegram_security_authorization_intents_tgsec_intent_no_execution_entry_path"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["telegram_security_action_receipts.receipt_id"],
            name=op.f(
                "fk_telegram_security_authorization_intents_receipt_id_telegram_security_action_receipts"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "intent_id", name=op.f("pk_telegram_security_authorization_intents")
        ),
        sa.UniqueConstraint("organization_id", "intent_id", name="uq_tgsec_intents_org_id"),
    )
    op.create_table(
        "watcher_scan_attempts",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("lineage_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("scan_scope", sa.String(length=200), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("lease_epoch", sa.Integer(), nullable=True),
        sa.Column("fencing_token", sa.Integer(), nullable=True),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sanitized_error", sa.String(length=255), nullable=True),
        sa.Column("recovery_disposition", sa.String(length=32), nullable=False),
        sa.Column("recovered_from_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("outcome_reason_code", sa.String(length=128), nullable=True),
        sa.Column("evaluation_input_hash", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "attempt_number >= 1", name=op.f("ck_watcher_scan_attempts_watcher_attempt_number_min")
        ),
        sa.ForeignKeyConstraint(
            ["lineage_id"],
            ["watcher_scan_lineages.lineage_id"],
            name=op.f("fk_watcher_scan_attempts_lineage_id_watcher_scan_lineages"),
        ),
        sa.PrimaryKeyConstraint("attempt_id", name=op.f("pk_watcher_scan_attempts")),
        sa.UniqueConstraint(
            "organization_id", "attempt_id", name="uq_watcher_scan_attempts_org_attempt"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "lineage_id",
            "attempt_number",
            name="uq_watcher_scan_attempts_org_lineage_number",
        ),
    )
    op.create_index(
        op.f("ix_watcher_scan_attempts_lineage_id"),
        "watcher_scan_attempts",
        ["lineage_id"],
        unique=False,
    )
    op.create_index(
        "ix_watcher_scan_attempts_org_scope_started",
        "watcher_scan_attempts",
        ["organization_id", "scan_scope", "started_at"],
        unique=False,
    )
    op.create_table(
        "watcher_scheduled_scans",
        sa.Column("scheduled_scan_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("scan_scope", sa.String(length=200), nullable=False),
        sa.Column("lineage_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["lineage_id"],
            ["watcher_scan_lineages.lineage_id"],
            name=op.f("fk_watcher_scheduled_scans_lineage_id_watcher_scan_lineages"),
        ),
        sa.PrimaryKeyConstraint("scheduled_scan_id", name=op.f("pk_watcher_scheduled_scans")),
        sa.UniqueConstraint(
            "organization_id", "scheduled_scan_id", name="uq_watcher_scheduled_scans_org_id"
        ),
    )
    op.create_index(
        "ix_watcher_scheduled_scans_org_scope",
        "watcher_scheduled_scans",
        ["organization_id", "scan_scope"],
        unique=False,
    )
    op.create_index(
        "uq_watcher_scheduled_scans_org_key_null_principal",
        "watcher_scheduled_scans",
        ["organization_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("principal_id IS NULL"),
    )
    op.create_index(
        "uq_watcher_scheduled_scans_org_principal_key",
        "watcher_scheduled_scans",
        ["organization_id", "principal_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("principal_id IS NOT NULL"),
    )
    op.create_table(
        "watcher_source_fetch_attempts",
        sa.Column("fetch_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("scan_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("lineage_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("scan_scope", sa.String(length=200), nullable=False),
        sa.Column("lease_epoch", sa.Integer(), nullable=True),
        sa.Column("fencing_token", sa.Integer(), nullable=True),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=128), nullable=True),
        sa.Column("source_freshness_token", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sanitized_error", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["scan_attempt_id"],
            ["watcher_scan_attempts.attempt_id"],
            name=op.f("fk_watcher_source_fetch_attempts_scan_attempt_id_watcher_scan_attempts"),
        ),
        sa.PrimaryKeyConstraint("fetch_attempt_id", name=op.f("pk_watcher_source_fetch_attempts")),
        sa.UniqueConstraint(
            "organization_id", "fetch_attempt_id", name="uq_watcher_source_fetch_org_id"
        ),
    )
    op.create_index(
        "ix_watcher_source_fetch_scan_attempt",
        "watcher_source_fetch_attempts",
        ["scan_attempt_id"],
        unique=False,
    )
    op.create_table(
        "watcher_subscription_eval_attempts",
        sa.Column("subscription_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("scan_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("lineage_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("scan_scope", sa.String(length=200), nullable=False),
        sa.Column("lease_epoch", sa.Integer(), nullable=True),
        sa.Column("fencing_token", sa.Integer(), nullable=True),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=128), nullable=True),
        sa.Column("evidence_validity_token", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sanitized_error", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["scan_attempt_id"],
            ["watcher_scan_attempts.attempt_id"],
            name=op.f(
                "fk_watcher_subscription_eval_attempts_scan_attempt_id_watcher_scan_attempts"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "subscription_attempt_id", name=op.f("pk_watcher_subscription_eval_attempts")
        ),
        sa.UniqueConstraint(
            "organization_id", "subscription_attempt_id", name="uq_watcher_sub_eval_org_id"
        ),
    )
    op.create_index(
        "ix_watcher_sub_eval_scan_attempt",
        "watcher_subscription_eval_attempts",
        ["scan_attempt_id"],
        unique=False,
    )


def downgrade() -> None:

    op.drop_index(
        "ix_watcher_sub_eval_scan_attempt", table_name="watcher_subscription_eval_attempts"
    )
    op.drop_table("watcher_subscription_eval_attempts")
    op.drop_index(
        "ix_watcher_source_fetch_scan_attempt", table_name="watcher_source_fetch_attempts"
    )
    op.drop_table("watcher_source_fetch_attempts")
    op.drop_index(
        "uq_watcher_scheduled_scans_org_principal_key", table_name="watcher_scheduled_scans"
    )
    op.drop_index(
        "uq_watcher_scheduled_scans_org_key_null_principal", table_name="watcher_scheduled_scans"
    )
    op.drop_index("ix_watcher_scheduled_scans_org_scope", table_name="watcher_scheduled_scans")
    op.drop_table("watcher_scheduled_scans")
    op.drop_index("ix_watcher_scan_attempts_org_scope_started", table_name="watcher_scan_attempts")
    op.drop_index(op.f("ix_watcher_scan_attempts_lineage_id"), table_name="watcher_scan_attempts")
    op.drop_table("watcher_scan_attempts")
    op.drop_table("telegram_security_authorization_intents")
    op.drop_table("watcher_worker_leases")
    op.drop_index("ix_watcher_scan_lineages_org_scope", table_name="watcher_scan_lineages")
    op.drop_table("watcher_scan_lineages")
    op.drop_index(
        op.f("ix_watcher_policy_versions_organization_id"), table_name="watcher_policy_versions"
    )
    op.drop_table("watcher_policy_versions")
    op.drop_index(
        "ix_watcher_observability_events_org_scope", table_name="watcher_observability_events"
    )
    op.drop_table("watcher_observability_events")
    op.drop_table("watcher_heartbeats")
    op.drop_table("watcher_health_snapshots")
    op.drop_index("ix_tgsec_outbox_claim", table_name="telegram_security_outbox")
    op.drop_table("telegram_security_outbox")
    op.drop_index(
        "ix_tgsec_challenges_org_user_bot_state",
        table_name="telegram_security_enrollment_challenges",
    )
    op.drop_index(
        "ix_tgsec_challenges_binding_id", table_name="telegram_security_enrollment_challenges"
    )
    op.drop_table("telegram_security_enrollment_challenges")
    op.drop_index("uq_tgsec_bindings_active_org_user", table_name="telegram_security_bindings")
    op.drop_index("uq_tgsec_bindings_active_bot_tg_user", table_name="telegram_security_bindings")
    op.drop_index("uq_tgsec_bindings_active_bot_chat", table_name="telegram_security_bindings")
    op.drop_table("telegram_security_bindings")
    op.drop_index("ix_tgsec_audit_org_at", table_name="telegram_security_audit_events")
    op.drop_table("telegram_security_audit_events")
    op.drop_index("uq_tgsec_receipts_bot_callback", table_name="telegram_security_action_receipts")
    op.drop_table("telegram_security_action_receipts")
    op.drop_table("telegram_security_action_nonces")
