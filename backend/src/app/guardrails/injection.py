"""Prompt injection guardrail — deterministic checks with pluggable classifier hook."""

from __future__ import annotations

from collections.abc import Callable

from app.guardrails.patterns import PatternRule, compile_rules, match_rules
from app.guardrails.types import GuardrailInput, GuardrailResult, GuardrailSeverity

_INJECTION_SPECS: list[tuple[str, str, str]] = [
    (
        "ignore_previous_instructions",
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        "Attempt to ignore prior instructions",
    ),
    (
        "reveal_system_prompt",
        r"(show|reveal|print|dump|display).{0,30}system\s+prompt",
        "Attempt to reveal system prompt",
    ),
    (
        "bypass_approval_workflow",
        r"bypass\s+(the\s+)?(approval|human\s+approval)",
        "Attempt to bypass approval workflow",
    ),
    (
        "disable_risk_checks",
        r"(disable|turn\s+off|skip|bypass)\s+(the\s+)?risk\s+(check|engine|gate)",
        "Attempt to disable risk checks",
    ),
    (
        "force_tool_execution",
        r"force\s+(tool|function)\s+(call|execution|invoke)",
        "Attempt to force tool execution",
    ),
    (
        "force_real_exchange",
        r"(enable|force|run)\s+.{0,20}(real|live)\s+(exchange\s+)?(trade|execution|order)",
        "Attempt to force real exchange execution",
    ),
    (
        "reveal_secrets",
        r"(reveal|show|dump|print).{0,20}(api\s*key|secret|credential|password|token)"
        r"|sk-[a-zA-Z0-9]{10,}",
        "Attempt to reveal secrets or API keys",
    ),
    (
        "override_system_rules",
        r"override\s+(developer|system|safety)\s+rules",
        "Attempt to override developer or system rules",
    ),
    (
        "manipulate_tool_schemas",
        r"(manipulate|alter|modify|change)\s+tool\s+schema",
        "Attempt to manipulate tool schemas",
    ),
    (
        "exfiltrate_hidden_context",
        r"(exfiltrat|leak|dump).{0,20}(hidden|internal)\s+context",
        "Attempt to exfiltrate hidden context",
    ),
]

_DEFAULT_RULES = compile_rules(_INJECTION_SPECS)

_BLOCK_SAFE_MESSAGE = (
    "Your request was blocked because it appears to manipulate system safety controls. "
    "AlphaTrade AI requires human approval, deterministic risk checks, and paper-only "
    "execution in this release."
)

ClassifierFn = Callable[[GuardrailInput], GuardrailResult | None]


class PromptInjectionGuardrail:
    """Detect prompt-injection and jailbreak patterns in user input."""

    def __init__(
        self,
        rules: list[PatternRule] | None = None,
        classifier: ClassifierFn | None = None,
    ) -> None:
        self._rules = rules if rules is not None else _DEFAULT_RULES
        self._classifier = classifier

    def evaluate(self, data: GuardrailInput) -> GuardrailResult:
        """Return a structured verdict for the user message."""
        if self._classifier is not None:
            llm_result = self._classifier(data)
            if llm_result is not None:
                return llm_result

        triggered = match_rules(data.message, self._rules)
        if not triggered:
            return GuardrailResult.pass_(reason="No prompt injection patterns detected.")

        return GuardrailResult(
            allowed=False,
            blocked=True,
            severity=GuardrailSeverity.CRITICAL,
            reason="Prompt injection or safety bypass attempt detected.",
            triggered_rules=triggered,
            safe_message=_BLOCK_SAFE_MESSAGE,
            audit_required=True,
            metadata={"guardrail": "prompt_injection"},
        )
