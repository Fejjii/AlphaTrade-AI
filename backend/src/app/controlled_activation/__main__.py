"""Print the package rollback. It does not apply the plan or send Telegram."""

from __future__ import annotations

import sys

from app.controlled_activation.rollback import plan_package_rollback, rollback_refuses_apply


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--self-check"]:
        plan = plan_package_rollback()
        text = "\n".join(step.action for step in plan)
        required = (
            "PERPETUAL_EVIDENCE_SOURCE=replay",
            "WATCHER_ORCHESTRATION_ENABLED=false",
            "TELEGRAM_PAPER_ACTIVATION_ARMED=false",
            "ENABLE_REAL_TRADING=false",
            "Do not downgrade Alembic",
            "Do not delete database rows",
        )
        if any(item not in text and item not in rollback_refuses_apply() for item in required):
            print("FAIL: package rollback is missing a pin", file=sys.stderr)
            return 1
        if "ENABLE_REAL_TRADING=true" in text:
            print("FAIL: rollback enables real trading", file=sys.stderr)
            return 1
        print("controlled paper activation rollback self-check passed")
        return 0
    if "--apply" in args:
        print(rollback_refuses_apply(), file=sys.stderr)
        return 2
    for step in plan_package_rollback():
        print(f"{step.order}. {step.action}")
    print("NOT APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
