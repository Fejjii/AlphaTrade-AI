#!/usr/bin/env python3
"""Stdlib health posture for paper Watcher.

Disarmed (both Watcher flags false) is the default and is safe.
Armed paper monitoring (both flags true, outside production) is safe.
Legacy market watcher and Telegram must stay false. Real trading must stay false.

This script does not activate Watcher and does not read secrets.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping

_TELEGRAM_AND_LEGACY = (
    "market_watcher_enabled",
    "market_watcher_bridge_enabled",
    "telegram_alerts_enabled",
    "telegram_interaction_enabled",
    "automatic_telegram_delivery_enabled",
)


def health_payload_errors(payload: Mapping[str, object]) -> tuple[str, ...]:
    errors: list[str] = []
    if payload.get("execution_mode") != "paper":
        errors.append("execution_mode")
    if payload.get("real_trading_enabled") is not False:
        errors.append("real_trading_enabled")
    exchange_mode = payload.get("exchange_mode")
    if exchange_mode not in (None, "paper_internal", "paper_exchange_demo"):
        errors.append("exchange_mode")
    for flag in _TELEGRAM_AND_LEGACY:
        if flag in payload and payload.get(flag) is not False:
            errors.append(flag)
    if "watcher_orchestration_enabled" in payload or "watcher_paper_staging_activation" in payload:
        orchestration = bool(payload.get("watcher_orchestration_enabled"))
        armed = bool(payload.get("watcher_paper_staging_activation"))
        if orchestration != armed:
            errors.append("watcher_paper_activation_pair")
        if orchestration and payload.get("environment") == "production":
            errors.append("production_watcher")
    return tuple(errors)


def _self_check() -> int:
    disarmed = {
        "execution_mode": "paper",
        "real_trading_enabled": False,
        "exchange_mode": "paper_internal",
        "environment": "staging",
        "watcher_orchestration_enabled": False,
        "watcher_paper_staging_activation": False,
        "telegram_alerts_enabled": False,
        "market_watcher_enabled": False,
    }
    armed = {
        **disarmed,
        "watcher_orchestration_enabled": True,
        "watcher_paper_staging_activation": True,
    }
    if health_payload_errors(disarmed) or health_payload_errors(armed):
        print("FAIL: expected disarmed and armed paper postures to pass", file=sys.stderr)
        return 1
    mismatched = {**disarmed, "watcher_orchestration_enabled": True}
    trading = {**disarmed, "real_trading_enabled": True}
    production = {**armed, "environment": "production"}
    if not health_payload_errors(mismatched):
        print("FAIL: unpaired orchestration was accepted", file=sys.stderr)
        return 1
    if "real_trading_enabled" not in health_payload_errors(trading):
        print("FAIL: real trading was accepted", file=sys.stderr)
        return 1
    if "production_watcher" not in health_payload_errors(production):
        print("FAIL: production arm was accepted", file=sys.stderr)
        return 1
    print("watcher paper health self-check passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--self-check"]:
        return _self_check()
    raw = args[0] if args else sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("FAIL: health payload is not JSON", file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print("FAIL: health payload must be an object", file=sys.stderr)
        return 1
    errors = health_payload_errors(payload)
    if errors:
        print("FAIL: " + ", ".join(errors), file=sys.stderr)
        return 1
    print(
        "  OK: paper mode, real_trading_enabled=false, "
        f"watcher_orchestration_enabled={payload.get('watcher_orchestration_enabled')}, "
        f"watcher_paper_staging_activation={payload.get('watcher_paper_staging_activation')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
