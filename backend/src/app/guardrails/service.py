"""Facade wiring all runtime guardrails (deterministic today, LLM-ready tomorrow)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.guardrails.injection import PromptInjectionGuardrail
from app.guardrails.moderation import ModerationGuardrail
from app.guardrails.output_validation import OutputValidationGuardrail
from app.guardrails.trading_policy import TradingPolicyGuardrail
from app.guardrails.types import GuardrailInput, GuardrailResult


@dataclass
class GuardrailService:
    """Injectable guardrail bundle used by LangGraph nodes at runtime."""

    prompt_injection: PromptInjectionGuardrail = field(default_factory=PromptInjectionGuardrail)
    moderation: ModerationGuardrail = field(default_factory=ModerationGuardrail)
    trading_policy: TradingPolicyGuardrail = field(default_factory=TradingPolicyGuardrail)
    output_validation: OutputValidationGuardrail = field(default_factory=OutputValidationGuardrail)

    def check_prompt_injection(self, data: GuardrailInput) -> GuardrailResult:
        return self.prompt_injection.evaluate(data)

    def check_moderation(self, data: GuardrailInput) -> GuardrailResult:
        return self.moderation.evaluate(data)

    def check_trading_policy(self, data: GuardrailInput) -> GuardrailResult:
        return self.trading_policy.evaluate(data)

    def validate_output(self, data: GuardrailInput) -> GuardrailResult:
        return self.output_validation.evaluate(data)

    def check_tool_bypass_attempt(self, data: GuardrailInput) -> GuardrailResult:
        """Ensure tools cannot be used to bypass upstream guardrails."""
        injection = self.check_prompt_injection(data)
        if injection.blocked:
            return injection
        moderation = self.check_moderation(data)
        if moderation.blocked:
            return moderation
        return GuardrailResult.pass_(reason="No tool bypass detected.")
