"""Operator CLI for preflight and rollback. It does not send Telegram messages."""

from __future__ import annotations

import argparse
import json
import sys

from app.core.config import get_settings
from app.telegram_activation.preflight import defaults_are_safe, run_preflight
from app.telegram_activation.rollback import plan_rollback, rollback_refuses_apply


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Paper Telegram activation checks")
    sub = parser.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser("preflight")
    preflight.add_argument(
        "--expect-disabled",
        action="store_true",
        help="Exit 0 only when defaults are safe and the process is not armable.",
    )
    preflight.add_argument(
        "--expect-armable",
        action="store_true",
        help="Exit 0 only when preflight would allow arming. Does not arm.",
    )
    run = sub.add_parser("run", help="Drain the paper outbox and poll. Does not trade.")
    run.add_argument(
        "--once",
        action="store_true",
        help="Run a single drain/poll cycle and exit.",
    )
    rollback = sub.add_parser("rollback")
    rollback.add_argument(
        "--apply",
        action="store_true",
        help="Refused. Rollback of environment and deploy is a human action.",
    )
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(once=bool(args.once))
    if args.command == "rollback":
        return _rollback(apply=bool(args.apply))
    return _preflight(
        expect_disabled=bool(args.expect_disabled),
        expect_armable=bool(args.expect_armable),
    )


def _preflight(*, expect_disabled: bool, expect_armable: bool) -> int:
    settings = get_settings()
    report = run_preflight(settings=settings)
    payload = report.model_dump(mode="json")
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if expect_armable:
        return 0 if report.runtime_armable else 1
    if expect_disabled:
        safe = defaults_are_safe(settings) and not report.runtime_armable
        return 0 if safe else 1
    return 0 if report.defaults_safe or report.runtime_armable else 1


def _run(*, once: bool) -> int:
    """Paper Telegram process. Idle and heartbeat when disarmed. Does not trade."""

    from app.core.logging import configure_logging
    from app.core.paper_safety import assert_execution_capable_composition_root
    from app.db.session import get_session_factory
    from app.telegram_activation.runtime import build_telegram_runtime

    settings = get_settings()
    configure_logging(log_level=settings.log_level, json_logs=settings.log_json)
    assert_execution_capable_composition_root(settings)
    runtime = build_telegram_runtime(settings, get_session_factory())
    if once:
        runtime.run_cycle()
        return 0
    runtime.run_forever()
    return 0


def _rollback(*, apply: bool) -> int:
    if apply:
        print(rollback_refuses_apply(), file=sys.stderr)
        return 2
    plan = plan_rollback()
    for step in plan.steps:
        print(f"{step.order}. {step.action}")
    settings = get_settings()
    if not defaults_are_safe(settings):
        print("Current process defaults are not the safe disabled posture.", file=sys.stderr)
        return 1
    print("Process defaults are disarmed. No environment file was edited.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
