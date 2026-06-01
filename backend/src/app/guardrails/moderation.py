"""Content moderation guardrail for reckless trading and policy abuse."""

from __future__ import annotations

from collections.abc import Callable

from app.guardrails.patterns import PatternRule, compile_rules, match_rules
from app.guardrails.types import GuardrailInput, GuardrailResult, GuardrailSeverity

_MODERATION_SPECS: list[tuple[str, str, str]] = [
    (
        "guaranteed_profit",
        r"guaranteed\s+profit|risk[- ]?free\s+profit|100\s*%\s+win",
        "Guaranteed profit claim",
    ),
    (
        "all_in_request",
        r"go\s+all\s+in|all[- ]?in\s+(on|into)|yolo\s+(entire|whole)\s+account",
        "All-in position request",
    ),
    (
        "unsafe_leverage",
        r"\b(50|75|100|125)x\s+leverage\b|max(imum)?\s+leverage\s+now",
        "Unsafe leverage request",
    ),
    (
        "bypass_stop_loss",
        r"(remove|disable|skip|bypass)\s+(the\s+)?stop[- ]?loss",
        "Request to bypass stop loss",
    ),
    (
        "revenge_trading",
        r"revenge\s+trad|get\s+back\s+at\s+(the\s+)?market|win\s+it\s+all\s+back\s+now",
        "Revenge trading language",
    ),
    (
        "emotional_overtrading",
        r"\bfomo\b|panic\s+sell\s+everything|emotional\s+overtrad",
        "Emotional overtrading",
    ),
    (
        "autonomous_real_money",
        r"fully\s+autonomous.{0,30}(real\s+money|live\s+account|real\s+exchange)",
        "Autonomous real-money execution request",
    ),
    (
        "hide_risk_or_losses",
        r"hide\s+(the\s+)?(loss|risk)|conceal\s+(loss|drawdown)",
        "Request to hide risk or losses",
    ),
    (
        "ignore_playbook",
        r"ignore\s+(the\s+)?(trading\s+)?playbook",
        "Request to ignore trading playbook",
    ),
    (
        "manipulate_audit_logs",
        r"(manipulate|alter|delete|tamper\s+with)\s+(the\s+)?(audit|log)s?",
        "Request to manipulate logs or audit records",
    ),
]

_BLOCK_RULES = frozenset(
    {
        "guaranteed_profit",
        "all_in_request",
        "autonomous_real_money",
        "hide_risk_or_losses",
        "ignore_playbook",
        "manipulate_audit_logs",
    }
)

_WARN_RULES = frozenset(
    {
        "unsafe_leverage",
        "bypass_stop_loss",
        "revenge_trading",
        "emotional_overtrading",
    }
)

_DEFAULT_RULES = compile_rules(_MODERATION_SPECS)

_BLOCK_SAFE_MESSAGE = (
    "Request blocked by moderation policy. This platform does not provide guaranteed "
    "profits, reckless risk advice, or autonomous real-money execution."
)

ClassifierFn = Callable[[GuardrailInput], GuardrailResult | None]


class ModerationGuardrail:
    """Block or warn on high-risk user content before orchestration continues."""

    def __init__(
        self,
        rules: list[PatternRule] | None = None,
        classifier: ClassifierFn | None = None,
    ) -> None:
        self._rules = rules if rules is not None else _DEFAULT_RULES
        self._classifier = classifier

    def evaluate(self, data: GuardrailInput) -> GuardrailResult:
        if self._classifier is not None:
            llm_result = self._classifier(data)
            if llm_result is not None:
                return llm_result

        triggered = match_rules(data.message, self._rules)
        if not triggered:
            return GuardrailResult.pass_(reason="No moderation issues detected.")

        block_hits = [r for r in triggered if r in _BLOCK_RULES]
        warn_hits = [r for r in triggered if r in _WARN_RULES]

        if block_hits:
            return GuardrailResult(
                allowed=False,
                blocked=True,
                severity=GuardrailSeverity.HIGH,
                reason="Moderation policy violation.",
                triggered_rules=triggered,
                safe_message=_BLOCK_SAFE_MESSAGE,
                audit_required=True,
                metadata={"guardrail": "moderation", "block_rules": block_hits},
            )

        if warn_hits:
            return GuardrailResult(
                allowed=True,
                blocked=False,
                severity=GuardrailSeverity.MEDIUM,
                reason="Moderation warning: reckless trading language detected.",
                triggered_rules=triggered,
                safe_message=(
                    "Proceed with caution. Reckless leverage, revenge trading, and "
                    "emotional sizing violate the trading playbook."
                ),
                audit_required=True,
                metadata={"guardrail": "moderation", "warn_rules": warn_hits},
            )

        return GuardrailResult(
            allowed=False,
            blocked=True,
            severity=GuardrailSeverity.HIGH,
            reason="Moderation policy violation.",
            triggered_rules=triggered,
            safe_message=_BLOCK_SAFE_MESSAGE,
            audit_required=True,
        )
