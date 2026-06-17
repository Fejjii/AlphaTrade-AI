"""Sanitize retrieved RAG/journal snippets before narrative LLM context (Slice 40C)."""

from __future__ import annotations

from app.guardrails.injection import PromptInjectionGuardrail
from app.guardrails.types import GuardrailInput

_INJECTION = PromptInjectionGuardrail()


def sanitize_retrieved_snippet(snippet: str, *, max_len: int = 200) -> str:
    """Re-scan and quote untrusted retrieved text so it cannot act as instructions."""
    text = (snippet or "").strip()[:max_len]
    if not text:
        return ""
    result = _INJECTION.evaluate(GuardrailInput(message=text))
    if result.blocked:
        return "[REDACTED_UNTRUSTED_RETRIEVED_CONTENT]"
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'[UNTRUSTED_RETRIEVED_CONTEXT] "{escaped}" [/UNTRUSTED_RETRIEVED_CONTEXT]'
