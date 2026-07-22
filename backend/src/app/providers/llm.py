"""OpenAI-compatible LLM provider abstraction."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import httpx
import structlog

from app.providers.base import BaseMockProvider, ProviderHealth, ProviderKind, ProviderStatus

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMCompletionRequest:
    messages: list[LLMMessage]
    model: str
    temperature: float = 0.0
    max_tokens: int = 512
    response_format: dict[str, Any] | None = None


@dataclass(frozen=True)
class LLMCompletionResult:
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    fallback_used: bool = False
    parsed_json: dict[str, Any] | None = None


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    kind: ProviderKind

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult: ...

    def status(self) -> ProviderStatus: ...


class MockLLMProvider(BaseMockProvider):
    """Deterministic LLM responses for offline tests and fallback mode."""

    def __init__(self) -> None:
        super().__init__(
            "mock-llm",
            ProviderKind.LLM,
            detail="Deterministic mock LLM — no external API calls.",
        )

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        system_text = next((m.content for m in request.messages if m.role == "system"), "")
        user_text = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
        if "__narrative_task__:" in system_text:
            payload = self._mock_narrative_payload(system_text, user_text)
        else:
            summary = user_text[:120] or "No user message."
            payload = {
                "summary": f"Mock analysis for: {summary}",
                "setup_type": "deterministic_scaffold",
                "evidence": ["Strategy signals evaluated deterministically."],
            }
        content = json.dumps(payload)
        input_tokens = max(len(content) // 4, 1)
        return LLMCompletionResult(
            content=content,
            model=request.model,
            provider=self.name,
            input_tokens=input_tokens,
            output_tokens=len(content) // 4,
            latency_ms=1.0,
            fallback_used=True,
            parsed_json=payload,
        )

    def _mock_narrative_payload(self, system_text: str, user_text: str) -> dict[str, Any]:
        """Deterministic narrative JSON for offline tests and fallback mode."""
        from app.guardrails.testing import TEST_INVALID_NARRATIVE, TEST_UNSAFE_NARRATIVE

        combined = f"{system_text} {user_text}"
        if TEST_INVALID_NARRATIVE in combined:
            return {"invalid": True}
        if TEST_UNSAFE_NARRATIVE in combined:
            return {
                "summary": "Guaranteed profit on this setup — buy now at market.",
                "setup_interpretation": "All-in now.",
                "evidence_explanation": "Sure win.",
                "risk_explanation": "Low risk guaranteed.",
                "invalidation_explanation": "N/A",
                "next_decision_point": "Enter immediately.",
                "caution_notes": [],
                "limitations": [],
                "paper_mode_disclaimer": "Paper mode.",
                "citations_used": [],
            }

        approval_status = "not_required"
        risk_level = "medium"
        market_quality = "mock"
        pending_markers = ('"approval_status": "pending"', '"approval_status":"pending"')
        if any(m in system_text for m in pending_markers):
            approval_status = "pending"
        if '"approval_status": "blocked"' in system_text:
            approval_status = "blocked"
        if '"risk_level": "high"' in system_text or '"risk_level":"high"' in system_text:
            risk_level = "high"
        elif '"risk_level": "medium"' in system_text or '"risk_level":"medium"' in system_text:
            risk_level = "medium"
        elif '"risk_level": "low"' in system_text or '"risk_level":"low"' in system_text:
            risk_level = "low"
        if '"market_data_quality": "stale"' in system_text:
            market_quality = "stale"

        data_disclosure = (
            "Mock market data — prices are not live."
            if market_quality == "mock"
            else "Stale market data — verify timestamps before acting."
        )
        has_proposal = '"has_trade_proposal": true' in system_text
        invalidation = (
            "Invalidation: close below stop or HTF structure breaks."
            if has_proposal
            else "No trade proposal — invalidation not applicable."
        )

        return {
            "summary": (
                "Mock narrative clarifies the deterministic analysis without changing facts. "
                f"{data_disclosure}"
            ),
            "setup_interpretation": "Deterministic setup interpretation from structured context.",
            "evidence_explanation": "Evidence follows strategy signals and indicator context.",
            "risk_explanation": (
                f"Risk level {risk_level} per deterministic engine; approval {approval_status}."
            ),
            "invalidation_explanation": invalidation,
            "next_decision_point": "Review plan; human approval required before paper execution.",
            "caution_notes": [
                "Mock LLM narrative — deterministic layer remains authoritative.",
                f"Approval status: {approval_status}.",
            ],
            "limitations": [
                "Real exchange execution disabled.",
                data_disclosure,
                f"Market data quality: {market_quality}.",
            ],
            "paper_mode_disclaimer": (
                "Paper mode only — no real exchange execution. "
                "Approval required for sensitive actions."
            ),
            "citations_used": ["mock-citation-1: playbook excerpt"],
        }


class OpenAILLMProvider:
    """OpenAI-compatible chat completions via HTTP."""

    name = "openai-llm"
    kind = ProviderKind.LLM

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        fallback: MockLLMProvider | None = None,
        timeout_seconds: float = 30.0,
        fail_closed: bool = False,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_model = model
        self._fail_closed = fail_closed
        self._fallback = None if fail_closed else (fallback or MockLLMProvider())
        self._timeout = timeout_seconds

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        from app.core.errors import ServiceUnavailableError

        if not self._api_key:
            if self._fail_closed or self._fallback is None:
                raise ServiceUnavailableError(
                    "LLM provider is unavailable.",
                    details={"reason": "openai_api_key_missing", "provider": self.name},
                )
            return self._fallback.complete(request)

        started = time.perf_counter()
        body: dict[str, Any] = {
            "model": request.model or self._default_model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.response_format is not None:
            body["response_format"] = request.response_format

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            logger.warning("openai_llm_request_failed", error=type(exc).__name__)
            if self._fail_closed or self._fallback is None:
                raise ServiceUnavailableError(
                    "LLM provider is unavailable.",
                    details={"reason": "openai_llm_unavailable", "provider": self.name},
                ) from exc
            result = self._fallback.complete(request)
            return LLMCompletionResult(
                content=result.content,
                model=result.model,
                provider=self.name,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                fallback_used=True,
                parsed_json=result.parsed_json,
            )

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = str(message.get("content") or "")
        usage = payload.get("usage") or {}
        parsed_json = _try_parse_json(content)
        return LLMCompletionResult(
            content=content,
            model=str(payload.get("model") or request.model),
            provider=self.name,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=latency_ms,
            fallback_used=False,
            parsed_json=parsed_json,
        )

    def status(self) -> ProviderStatus:
        if not self._api_key:
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.UNAVAILABLE,
                using_fallback=not self._fail_closed,
                is_mock=False,
                detail=(
                    "OPENAI_API_KEY not configured."
                    if self._fail_closed
                    else "OPENAI_API_KEY not configured — using mock-llm fallback."
                ),
            )
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                if response.status_code < 500:
                    return ProviderStatus(
                        name=self.name,
                        kind=self.kind,
                        health=ProviderHealth.HEALTHY,
                        using_fallback=False,
                        is_mock=False,
                        detail=f"OpenAI-compatible LLM ({self._default_model}).",
                    )
        except Exception as exc:
            logger.debug("openai_llm_status_degraded", error=str(exc))
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=(ProviderHealth.UNAVAILABLE if self._fail_closed else ProviderHealth.DEGRADED),
            using_fallback=not self._fail_closed,
            is_mock=False,
            detail=(
                "OpenAI API unreachable."
                if self._fail_closed
                else "OpenAI API unreachable — mock-llm fallback active at runtime."
            ),
        )


def _try_parse_json(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def validate_llm_json(
    parsed: dict[str, Any] | None,
    *,
    required_fields: tuple[str, ...] = ("summary",),
) -> bool:
    """Reject malformed LLM JSON before it enters agent state."""
    if parsed is None:
        return False
    return all(
        isinstance(parsed.get(name), str) and parsed[name].strip() for name in required_fields
    )
