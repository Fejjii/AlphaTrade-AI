#!/usr/bin/env python3
"""Print the operator prerequisites; optionally inspect a binding using SELECT.

Never imports a Telegram HTTP transport, starts polling, writes a binding, or
arms a worker. Run with backend dependencies/PYTHONPATH for --check-binding.
"""

import argparse
import json
import os
import re
from uuid import UUID

SAFE = {
    "ENABLE_REAL_TRADING": "false",
    "EXECUTION_MODE": "paper",
    "EXCHANGE_MODE": "paper_internal",
    "TELEGRAM_NETWORK_PERMITTED": "false",
    "TELEGRAM_PAPER_ACTIVATION_ARMED": "false",
    "TELEGRAM_INTERACTION_ENABLED": "false",
    "TELEGRAM_INBOUND_MODE": "off",
    "TELEGRAM_ALERTS_ENABLED": "false",
    "AUTOMATIC_TELEGRAM_DELIVERY_ENABLED": "false",
}
ENROLLMENT = {
    "ENVIRONMENT": "staging",
    "ENABLE_REAL_TRADING": "false",
    "EXECUTION_MODE": "paper",
    "EXCHANGE_MODE": "paper_internal",
    "PERPETUAL_EVIDENCE_SOURCE": "binance_usdm",
    "TELEGRAM_NETWORK_PERMITTED": "true (operator action only)",
    "TELEGRAM_INTERACTION_ENABLED": "true",
    "TELEGRAM_INBOUND_MODE": "polling",
    "TELEGRAM_PAPER_ACTIVATION_ARMED": "false",
    "TELEGRAM_ALERTS_ENABLED": "false",
    "AUTOMATIC_TELEGRAM_DELIVERY_ENABLED": "false",
    "TELEGRAM_WEBHOOK_SECRET": "empty",
    "TELEGRAM_BOT_ID": "numeric bot user id matching the token prefix",
    "TELEGRAM_BOT_TOKEN": "configured secret; never print",
    "DATABASE_URL": "migrated PostgreSQL; shared by API, Watcher and Telegram worker",
    "JWT_SECRET": "valid staging secret (existing deployment validation)",
    "GLOBAL_KILL_SWITCH_ACTIVE": (
        "false for enrollment; projection also requires tenant kill switch false"
    ),
}
PROJECTION = {
    **ENROLLMENT,
    "TELEGRAM_PAPER_ACTIVATION_ARMED": "true (operator action after verified enrollment)",
    "WATCHER_ORCHESTRATION_ENABLED": "true",
    "WATCHER_PAPER_STAGING_ACTIVATION": "true",
    "MARKET_WATCHER_ENABLED": "false",
    "MARKET_WATCHER_BRIDGE_ENABLED": "false",
    "MARKET_WATCHER_BRIDGE_AUTO_TICK": "false",
    "TELEGRAM_CHAT_ID": "exact verified private chat binding; chat id alone is insufficient",
}


def inspect_binding(environ):
    from sqlalchemy import create_engine, select

    from app.db.telegram_security import TelegramBindingRow

    # The accepted profile has PostgreSQL persistence. No schema creation or writes.
    url = environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        return {"state": "BLOCKED", "reason": "migrated_postgres_required"}
    try:
        org = UUID(environ["ACCEPTANCE_ORGANIZATION_ID"])
        user = UUID(environ["ACCEPTANCE_USER_ID"])
    except (KeyError, ValueError):
        return {"state": "BLOCKED", "reason": "expected_tenant_and_user_required"}
    engine = None
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 15})
        with engine.connect() as connection:
            rows = (
                connection.execute(
                    select(TelegramBindingRow.__table__).where(
                        TelegramBindingRow.bot_id == environ.get("TELEGRAM_BOT_ID", ""),
                        TelegramBindingRow.chat_id == environ.get("TELEGRAM_CHAT_ID", ""),
                        TelegramBindingRow.revoked_at.is_(None),
                    )
                )
                .mappings()
                .all()
            )
        if len(rows) != 1:
            return {"state": "BLOCKED", "reason": "exactly_one_active_binding_required"}
        row = rows[0]
        valid = (
            row["organization_id"] == org
            and row["user_id"] == user
            and row["state"] == "VERIFIED"
            and row["chat_type"] == "private"
            and row["verified_at"] is not None
            and "CLOSE" not in row["allowed_actions"]
        )
        return {
            "state": "VERIFIED_PRIVATE" if valid else "BLOCKED",
            "reason": "binding_verified" if valid else "binding_scope_or_authority_invalid",
        }
    except Exception:
        return {"state": "BLOCKED", "reason": "binding_database_unavailable"}
    finally:
        if engine is not None:
            engine.dispose()


def report(environ, binding=None):
    blockers = [
        f"{key}_must_be_{value}"
        for key, value in SAFE.items()
        if environ.get(key, "").lower() != value
    ]
    if environ.get("ENVIRONMENT") != "staging":
        blockers.append("ENVIRONMENT_must_be_staging")
    token = environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    bot_id = environ.get("TELEGRAM_BOT_ID", "").strip()
    match = re.match(r"^(\d{1,32}):\S+$", token)
    if not bot_id.isdigit() or match is None or match.group(1) != bot_id:
        blockers.append("numeric_bot_identity_and_matching_secret_required")
    if not environ.get("TELEGRAM_CHAT_ID", "").strip():
        blockers.append("verified_private_chat_id_required")
    binding = binding or {
        "state": "NOT_CHECKED",
        "reason": "use_check_binding_with_expected_tenant_and_user",
    }
    if binding["state"] != "VERIFIED_PRIVATE":
        blockers.append(binding["reason"])
    return {
        "status": "OPERATOR_REVIEW_REQUIRED" if not blockers else "BLOCKED",
        "network_activated": False,
        "execution_authority_changed": False,
        "blockers": blockers,
        "binding": binding,
        "required_current_safe_environment": SAFE,
        "operator_enrollment_environment": ENROLLMENT,
        "operator_projection_environment": PROJECTION,
        "additional_required_state": [
            "API and Telegram process share migrated PostgreSQL and the same accepted release SHA",
            "POST /telegram-paper/enrollment/start by intended tenant/user; "
            "unexpired single-use challenge",
            "Private /start <token> consumed by enrollment polling; verified binding not revoked",
            "telegram_enabled=true; effective Policy V2 includes the intended event/subscription",
            "Quality, symbol scope, cooldown and quiet hours permit the informational event",
            "Fresh heartbeat, matching durable polling cursor/lease and no dead-letter backlog",
            "Exact confirmation identity for paper mutation; bare confirmation has zero authority",
            "Existing Settings/deployment validation must pass; this report does not arm anything",
        ],
        "real_message": "NOT_TESTED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-binding", action="store_true")
    args = parser.parse_args()
    # Refuse inspection once the operator has changed the offline safety boundary.
    if os.environ.get("TELEGRAM_NETWORK_PERMITTED", "false").lower() != "false":
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": "network_must_be_disabled_for_preparation",
                    "network_activated": False,
                }
            )
        )
        return 2
    binding = inspect_binding(os.environ) if args.check_binding else None
    result = report(os.environ, binding)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "OPERATOR_REVIEW_REQUIRED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
