#!/usr/bin/env python3
"""Agent response quality evaluation (Slice 21).

Runs golden cases against the narrative guardrail and full agent graph (mock LLM).
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from app.core.config import Settings  # noqa: E402
from app.guardrails.narrative_validation import NarrativeValidationGuardrail  # noqa: E402
from app.services.agent_service import AgentInvokeContext, build_agent_service  # noqa: E402


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    detail: str


def _load_json(name: str) -> list[dict]:
    path = REPO_ROOT / "evaluation" / "datasets" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _evaluate_guardrail_cases() -> list[EvalResult]:
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
    return results


def _evaluate_agent_cases() -> list[EvalResult]:
    settings = Settings(
        log_json=False,
        provider_mode="mock",
        market_data_provider="mock",
        narrative_llm_enabled=True,
        openai_api_key="",
    )
    service = build_agent_service(settings)
    ctx = AgentInvokeContext(
        request_id="eval-req-001",
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        organization_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
    )
    results: list[EvalResult] = []
    for case in _load_json("agent_cases.json"):
        response = service.run(case["message"], ctx, symbol="BTCUSDT", timeframe="4h")
        text = (response.reply or "").lower()
        meta = response.narrative_meta
        passed = True
        details: list[str] = []

        for pattern in case.get("forbidden_patterns", []):
            if pattern.lower() in text:
                passed = False
                details.append(f"forbidden:{pattern}")

        for pattern in case.get("required_patterns", []):
            if pattern.lower() not in text:
                passed = False
                details.append(f"missing:{pattern}")

        expected_source = case.get("expect_narrative_source")
        if expected_source and (meta is None or meta.source != expected_source):
            passed = False
            details.append(f"source={meta.source if meta else None}")

        if case["id"] == "mock_data_disclosed" and response.analysis:
            if response.analysis.market_data_quality == "mock" and "mock" not in text:
                passed = False
                details.append("mock_quality_not_in_reply")

        if case["id"] == "invalidation_for_proposal" and response.analysis:
            if not response.analysis.invalidation and "invalidation" not in text:
                passed = False
                details.append("no_invalidation")

        if not details:
            details.append("ok")
        results.append(EvalResult(case["id"], passed, "; ".join(details)))
    return results


def main() -> int:
    results = _evaluate_guardrail_cases() + _evaluate_agent_cases()
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} {result.case_id}: {result.detail}")
    print(f"\nAgent evaluation: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
