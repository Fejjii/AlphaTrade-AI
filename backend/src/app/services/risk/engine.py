"""Risk engine: aggregates rule outcomes into a single deterministic verdict."""

from __future__ import annotations

from app.schemas.common import RiskAction, RiskSeverity
from app.schemas.risk import RiskCheckRequest, RiskCheckResult, TriggeredRule
from app.services.risk.limits import RiskLimits
from app.services.risk.rules import ALL_RULES, RiskEvaluationContext, default_is_weekend

_ACTION_RANK = {RiskAction.ALLOW: 0, RiskAction.WARN: 1, RiskAction.BLOCK: 2}
_SEVERITY_RANK = {
    RiskSeverity.INFO: 0,
    RiskSeverity.LOW: 1,
    RiskSeverity.MEDIUM: 2,
    RiskSeverity.HIGH: 3,
    RiskSeverity.CRITICAL: 4,
}


class RiskEngine:
    """Deterministic risk gate. The LLM may explain results but never overrides them."""

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self._limits = limits or RiskLimits()

    @property
    def limits(self) -> RiskLimits:
        return self._limits

    def evaluate(
        self,
        request: RiskCheckRequest,
        *,
        context: RiskEvaluationContext | None = None,
    ) -> RiskCheckResult:
        ctx = context or RiskEvaluationContext(is_weekend=default_is_weekend())
        triggered: list[TriggeredRule] = []

        for rule_fn in ALL_RULES:
            outcome = rule_fn(request, self._limits, ctx)
            if outcome is not None:
                triggered.append(outcome)

        if not triggered:
            return RiskCheckResult(
                action=RiskAction.ALLOW,
                severity=RiskSeverity.INFO,
                triggered_rules=[],
                explanation="All risk checks passed.",
                approval_required=False,
            )

        action = max((t.action for t in triggered), key=lambda a: _ACTION_RANK[a])
        severity = max((t.severity for t in triggered), key=lambda s: _SEVERITY_RANK[s])
        messages = "; ".join(t.message for t in triggered)
        approval_required = action in {RiskAction.WARN, RiskAction.BLOCK} or any(
            t.severity in {RiskSeverity.HIGH, RiskSeverity.CRITICAL} for t in triggered
        )

        suggested: dict[str, str] | None = None
        if action is not RiskAction.ALLOW:
            suggested = {
                "leverage": str(min(request.leverage, self._limits.max_leverage)),
                "note": "Reduce size and leverage; ensure stop loss is set.",
            }

        return RiskCheckResult(
            action=action,
            severity=severity,
            triggered_rules=triggered,
            explanation=messages,
            approval_required=approval_required,
            suggested_modification=suggested,
        )
