"""Hard trading safety policy enforced on proposals and orchestration context."""

from __future__ import annotations

from decimal import Decimal

from app.guardrails.patterns import compile_rules, match_rules
from app.guardrails.types import GuardrailInput, GuardrailResult, GuardrailSeverity

_MESSAGE_SPECS: list[tuple[str, str, str]] = [
    ("guaranteed_profit_language", r"guaranteed\s+profit|sure\s+win", "Guaranteed profit"),
    ("all_in_recommendation", r"go\s+all\s+in|all[- ]?in\s+recommend", "All-in recommendation"),
    ("oversized_leverage", r"\b(20|50|75|100)x\b", "Oversized leverage mention"),
    ("bypass_risk_engine", r"bypass\s+(the\s+)?risk\s+engine", "Risk engine bypass"),
    (
        "real_trading_mvp",
        r"execute\s+on\s+live\s+exchange|real\s+money\s+order\s+now",
        "Real trading",
    ),
    (
        "certainty_without_data",
        r"definitely\s+will\s+pump|certain\s+upside",
        "Unsupported certainty",
    ),
    (
        "average_down_emotionally",
        r"average\s+down\s+to\s+feel\s+better|double\s+down\s+out\s+of\s+anger",
        "Emotional averaging",
    ),
]

_MESSAGE_RULES = compile_rules(_MESSAGE_SPECS)
_MAX_LEVERAGE = Decimal("10")


class TradingPolicyGuardrail:
    """Enforce non-negotiable trading safety rules on state and proposals."""

    def evaluate(self, data: GuardrailInput) -> GuardrailResult:
        result = GuardrailResult.pass_(reason="Trading policy satisfied.")
        text = f"{data.message} {data.final_answer or ''}"
        triggered = match_rules(text, _MESSAGE_RULES)
        if triggered:
            result = result.merge(
                GuardrailResult.block(
                    rule_id=triggered[0],
                    reason="Trading policy language violation.",
                    severity=GuardrailSeverity.HIGH,
                    safe_message=(
                        "This request violates trading safety policy (no guarantees, "
                        "no all-in advice, no live execution in MVP)."
                    ),
                )
            )
            result.triggered_rules = triggered

        if data.has_trade_proposal and data.trade_proposal is not None:
            proposal_result = self._check_proposal(data)
            result = result.merge(proposal_result)

        return result

    def _check_proposal(self, data: GuardrailInput) -> GuardrailResult:
        proposal = data.trade_proposal
        assert proposal is not None
        triggered: list[str] = []

        if proposal.leverage > _MAX_LEVERAGE:
            triggered.append("oversized_leverage_proposal")

        if not proposal.exit.invalidation or proposal.exit.invalidation.strip().lower() in {
            "n/a",
            "none",
        }:
            triggered.append("missing_invalidation")

        if proposal.exit.stop_loss is None:
            triggered.append("missing_stop_loss")

        if proposal.risk_level is None:
            triggered.append("missing_risk_context")

        if proposal.confidence is None:
            triggered.append("missing_confidence")

        rationale = (proposal.rationale or "").lower()
        if any(p in rationale for p in ("guaranteed", "sure win", "can't lose")):
            triggered.append("guarantee_in_rationale")

        if triggered:
            return GuardrailResult(
                allowed=False,
                blocked=True,
                severity=GuardrailSeverity.HIGH,
                reason="Trade proposal failed trading policy checks.",
                triggered_rules=triggered,
                safe_message=(
                    "Trade proposal blocked: requires risk context, invalidation, "
                    "stop loss, and no guarantee language."
                ),
                audit_required=True,
                metadata={"guardrail": "trading_policy"},
            )
        return GuardrailResult.pass_()
