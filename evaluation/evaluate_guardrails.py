#!/usr/bin/env python3
"""Narrative guardrail evaluation (Slice 22)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from app.guardrails.narrative_validation import NarrativeValidationGuardrail  # noqa: E402


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    detail: str


def _load_json(name: str) -> list[dict]:
    path = REPO_ROOT / "evaluation" / "datasets" / name
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    validator = NarrativeValidationGuardrail()
    results: list[EvalResult] = []
    for case in _load_json("guardrail_cases.json"):
        outcome = validator.evaluate_text(case["text"])
        blocked = outcome.blocked
        passed = blocked == case["expect_blocked"]
        results.append(
            EvalResult(
                case["id"],
                passed,
                f"blocked={blocked} expected={case['expect_blocked']}",
            )
        )

    passed_count = sum(1 for r in results if r.passed)
    total = len(results)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} {result.case_id}: {result.detail}")
    print(f"\nGuardrail evaluation: {passed_count}/{total} passed")
    return 0 if passed_count == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
