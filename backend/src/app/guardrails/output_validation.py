"""Validate final agent outputs before returning to clients."""

from __future__ import annotations

import re

from app.guardrails.patterns import compile_rules, match_rules
from app.guardrails.types import GuardrailInput, GuardrailResult, GuardrailSeverity

_FORBIDDEN_SPECS: list[tuple[str, str, str]] = [
    ("guarantee_language", r"guaranteed\s+profit|sure\s+win|risk[- ]?free", "Guarantee language"),
    (
        "hidden_execution_claim",
        r"already\s+executed\s+on\s+exchange|order\s+placed\s+live|filled\s+on\s+binance",
        "Hidden execution claim",
    ),
]

_FORBIDDEN_RULES = compile_rules(_FORBIDDEN_SPECS)

_FALLBACK = (
    "I cannot return the prior response because it did not meet trading safety requirements. "
    "Ask for analysis that includes risk level, confidence, limitations, approval status, "
    "invalidation for any trade idea, and stop-loss context. Real exchange execution is "
    "disabled; paper mode requires explicit human approval."
)


class OutputValidationGuardrail:
    """Ensure trading-related replies include required safety fields."""

    def evaluate(self, data: GuardrailInput) -> GuardrailResult:
        text = (data.final_answer or "").strip()
        if not text:
            return GuardrailResult.block(
                rule_id="empty_output",
                reason="Empty agent output.",
                severity=GuardrailSeverity.HIGH,
                safe_message=_FALLBACK,
            )

        forbidden = match_rules(text, _FORBIDDEN_RULES)
        if forbidden:
            return GuardrailResult.block(
                rule_id=forbidden[0],
                reason="Output contains forbidden guarantee or execution claims.",
                severity=GuardrailSeverity.HIGH,
                safe_message=_FALLBACK,
                metadata={"forbidden_rules": forbidden},
            )

        if not self._is_trading_output(data, text):
            return GuardrailResult.pass_(reason="Non-trading output accepted.")

        missing = self._missing_trading_fields(data, text)
        if missing:
            return GuardrailResult(
                allowed=False,
                blocked=True,
                severity=GuardrailSeverity.HIGH,
                reason="Trading output missing required safety fields.",
                triggered_rules=missing,
                safe_message=_FALLBACK,
                audit_required=True,
                metadata={"guardrail": "output_validation", "missing": missing},
            )
        return GuardrailResult.pass_(reason="Trading output validated.")

    def _is_trading_output(self, data: GuardrailInput, text: str) -> bool:
        if data.has_trade_proposal:
            return True
        lowered = text.lower()
        return any(
            token in lowered
            for token in (
                "trade proposal",
                "approval status",
                "confidence",
                "risk",
                "stop loss",
                "invalidation",
            )
        )

    def _missing_trading_fields(self, data: GuardrailInput, text: str) -> list[str]:
        missing: list[str] = []
        lowered = text.lower()

        if not re.search(r"risk\s*level|risk_level", lowered):
            missing.append("risk_level")

        if "confidence" not in lowered and data.confidence is None:
            missing.append("confidence")

        if "limitation" not in lowered:
            missing.append("limitations")

        if "approval status" not in lowered and "approval_status" not in lowered:
            missing.append("approval_status")

        if data.has_trade_proposal and "invalidation" not in lowered:
            missing.append("invalidation")

        has_stop = "stop loss" in lowered or "stop-loss" in lowered
        has_no_trade_reason = any(
            phrase in lowered
            for phrase in (
                "no trade",
                "not take",
                "do not trade",
                "no executable proposal",
            )
        )
        if not has_stop and not has_no_trade_reason:
            missing.append("stop_loss_or_no_trade_reason")

        has_context = (
            "citation" in lowered
            or "retrieved context" in lowered
            or "playbook" in lowered
            or data.has_citations
        )
        if not has_context:
            missing.append("citations_or_context")

        return missing
