"""Validate LLM narrative output before merging with deterministic analysis."""

from __future__ import annotations

import re

from app.guardrails.patterns import compile_rules, match_rules
from app.guardrails.types import GuardrailResult, GuardrailSeverity
from app.schemas.narrative import TradingNarrativeDetail

_FORBIDDEN_SPECS: list[tuple[str, str, str]] = [
    ("guarantee_language", r"guaranteed\s+profit|sure\s+win|risk[- ]?free", "Guarantee language"),
    ("all_in_language", r"go\s+all\s+in|all[- ]?in\s+(?:now|trade|position)", "All-in language"),
    (
        "direct_order_instruction",
        r"place\s+(?:a\s+)?order|buy\s+now|sell\s+now|enter\s+at\s+market|submit\s+market\s+order",
        "Direct order instruction",
    ),
    (
        "hidden_execution_claim",
        r"already\s+executed\s+on\s+exchange|order\s+placed\s+live|filled\s+on\s+binance",
        "Hidden execution claim",
    ),
    (
        "false_market_data_claim",
        r"fully live with no limitations|perfect market data|no delays or gaps",
        "False market data quality claim",
    ),
]

_FORBIDDEN_RULES = compile_rules(_FORBIDDEN_SPECS)


class NarrativeValidationGuardrail:
    """Reject unsafe or fact-drifting LLM narrative before it reaches clients."""

    def evaluate_text(self, text: str) -> GuardrailResult:
        forbidden = match_rules(text, _FORBIDDEN_RULES)
        if forbidden:
            return GuardrailResult.block(
                rule_id=forbidden[0],
                reason="Narrative contains forbidden trading language.",
                severity=GuardrailSeverity.HIGH,
                audit_required=True,
                metadata={"guardrail": "narrative_validation", "forbidden_rules": forbidden},
            )
        return GuardrailResult.pass_(reason="Narrative text policy satisfied.")

    def evaluate_narrative(
        self,
        narrative: TradingNarrativeDetail,
        *,
        expected_risk_level: str | None,
        expected_approval_status: str,
        has_trade_proposal: bool,
        market_data_quality: str,
    ) -> GuardrailResult:
        """Validate structured narrative against deterministic facts."""
        combined = " ".join(
            [
                narrative.summary,
                narrative.setup_interpretation,
                narrative.evidence_explanation,
                narrative.risk_explanation,
                narrative.invalidation_explanation,
                narrative.next_decision_point,
                narrative.paper_mode_disclaimer,
                *narrative.caution_notes,
                *narrative.limitations,
            ]
        )
        text_result = self.evaluate_text(combined)
        if text_result.blocked:
            return text_result

        if expected_risk_level:
            risk_token = expected_risk_level.lower()
            combined_lower = combined.lower()
            has_risk = risk_token in combined_lower or f"risk level {risk_token}" in combined_lower
            if not has_risk:
                return GuardrailResult.block(
                    rule_id="risk_level_mismatch",
                    reason="Narrative must reference the deterministic risk level.",
                    severity=GuardrailSeverity.MEDIUM,
                    audit_required=True,
                    metadata={
                        "guardrail": "narrative_validation",
                        "expected_risk_level": expected_risk_level,
                    },
                )

        if expected_approval_status.lower() not in combined.lower():
            return GuardrailResult.block(
                rule_id="approval_status_missing",
                reason="Narrative must disclose approval status from deterministic analysis.",
                severity=GuardrailSeverity.MEDIUM,
                audit_required=True,
                metadata={
                    "guardrail": "narrative_validation",
                    "expected_approval_status": expected_approval_status,
                },
            )

        if has_trade_proposal and not narrative.invalidation_explanation.strip():
            return GuardrailResult.block(
                rule_id="invalidation_missing",
                reason="Trade proposal requires invalidation explanation in narrative.",
                severity=GuardrailSeverity.MEDIUM,
                audit_required=True,
                metadata={"guardrail": "narrative_validation"},
            )

        if market_data_quality in {"mock", "stale"}:
            quality_token = "mock" if market_data_quality == "mock" else "stale"
            if quality_token not in combined.lower():
                return GuardrailResult.block(
                    rule_id="market_data_quality_undisclosed",
                    reason="Narrative must disclose non-live market data quality.",
                    severity=GuardrailSeverity.MEDIUM,
                    audit_required=True,
                    metadata={
                        "guardrail": "narrative_validation",
                        "market_data_quality": market_data_quality,
                    },
                )

        if re.search(
            r"real\s+exchange\s+execution\s+enabled|live\s+order\s+placed|executed\s+on\s+exchange",
            combined,
            re.IGNORECASE,
        ):
            return GuardrailResult.block(
                rule_id="false_execution_claim",
                reason="Narrative must not claim real exchange execution.",
                severity=GuardrailSeverity.HIGH,
                audit_required=True,
                metadata={"guardrail": "narrative_validation"},
            )

        return GuardrailResult.pass_(reason="Narrative validated against deterministic facts.")
