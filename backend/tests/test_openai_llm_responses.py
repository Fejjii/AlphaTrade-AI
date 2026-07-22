"""Tests for OpenAI LLM Responses API routing and generation readiness."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.errors import ServiceUnavailableError
from app.providers.base import ProviderHealth
from app.providers.llm import (
    LLMCompletionRequest,
    LLMMessage,
    OpenAILLMProvider,
    model_requires_responses_api,
)


def _request(*, model: str = "gpt-5.6-sol", max_tokens: int = 32) -> LLMCompletionRequest:
    return LLMCompletionRequest(
        messages=[
            LLMMessage(role="system", content="Be brief."),
            LLMMessage(role="user", content="Say OK"),
        ],
        model=model,
        temperature=0.0,
        max_tokens=max_tokens,
    )


def _mock_client_with_response(response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    client.post.return_value = response
    client.get.return_value = response
    return client


def _http_response(
    *,
    status_code: int = 200,
    payload: dict[str, Any] | None = None,
    text: str = "",
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload if payload is not None else {}
    response.text = text
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error",
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
            response=httpx.Response(status_code, request=httpx.Request("POST", "https://x")),
        )
    else:
        response.raise_for_status = MagicMock()
    return response


class TestModelRouting:
    def test_gpt56_sol_requires_responses(self) -> None:
        assert model_requires_responses_api("gpt-5.6-sol") is True
        assert model_requires_responses_api("gpt-5.6") is True
        assert model_requires_responses_api("o3-mini") is True

    def test_classic_chat_model_keeps_completions(self) -> None:
        assert model_requires_responses_api("gpt-4o-mini") is False
        assert model_requires_responses_api("gpt-4.1") is False


class TestResponsesGeneration:
    def test_successful_responses_api_generation(self) -> None:
        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            fail_closed=True,
        )
        response = _http_response(
            payload={
                "model": "gpt-5.6-sol",
                "output_text": "OK",
                "usage": {"input_tokens": 3, "output_tokens": 1},
            }
        )
        client = _mock_client_with_response(response)
        with patch("httpx.Client", return_value=client):
            result = provider.complete(_request())
        assert result.content == "OK"
        assert result.fallback_used is False
        assert result.model == "gpt-5.6-sol"
        assert result.input_tokens == 3
        assert result.output_tokens == 1
        url = client.post.call_args.args[0]
        body = client.post.call_args.kwargs["json"]
        assert url.endswith("/responses")
        assert "messages" not in body
        assert body["model"] == "gpt-5.6-sol"
        assert body["max_output_tokens"] == 32
        assert body["store"] is False
        assert body["instructions"] == "Be brief."
        assert body["input"][0]["role"] == "user"
        assert "temperature" not in body
        assert body["reasoning"]["effort"] == "low"

    def test_json_object_maps_to_text_format(self) -> None:
        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            fail_closed=True,
        )
        response = _http_response(
            payload={"output_text": '{"summary":"x"}', "usage": {}, "model": "gpt-5.6-sol"}
        )
        client = _mock_client_with_response(response)
        with patch("httpx.Client", return_value=client):
            provider.complete(
                LLMCompletionRequest(
                    messages=[LLMMessage(role="user", content="json")],
                    model="gpt-5.6-sol",
                    response_format={"type": "json_object"},
                )
            )
        body = client.post.call_args.kwargs["json"]
        assert body["text"]["format"]["type"] == "json_object"

    def test_extracts_output_array_when_output_text_missing(self) -> None:
        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            fail_closed=True,
        )
        response = _http_response(
            payload={
                "model": "gpt-5.6-sol",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "hello"}],
                    }
                ],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )
        with patch("httpx.Client", return_value=_mock_client_with_response(response)):
            result = provider.complete(_request())
        assert result.content == "hello"


class TestResponsesFailures:
    def test_model_unavailable_404(self) -> None:
        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            fail_closed=True,
        )
        response = _http_response(
            status_code=404,
            payload={"error": {"code": "model_not_found", "type": "invalid_request_error"}},
        )
        with (
            patch("httpx.Client", return_value=_mock_client_with_response(response)),
            pytest.raises(ServiceUnavailableError) as exc_info,
        ):
            provider.complete(_request())
        assert exc_info.value.details["reason"] == "openai_llm_model_unavailable"
        assert exc_info.value.details["http_status"] == 404
        assert "sk-test" not in str(exc_info.value.details)

    def test_permission_failure_401(self) -> None:
        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            fail_closed=True,
        )
        response = _http_response(
            status_code=401,
            payload={"error": {"code": "invalid_api_key", "type": "invalid_request_error"}},
        )
        with (
            patch("httpx.Client", return_value=_mock_client_with_response(response)),
            pytest.raises(ServiceUnavailableError) as exc_info,
        ):
            provider.complete(_request())
        assert exc_info.value.details["reason"] == "openai_llm_permission_denied"

    def test_rate_limit_429(self) -> None:
        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            fail_closed=True,
            timeout_seconds=1.0,
        )
        response = _http_response(
            status_code=429,
            payload={"error": {"code": "rate_limit_exceeded", "type": "rate_limit_error"}},
        )
        with (
            patch("httpx.Client", return_value=_mock_client_with_response(response)),
            patch("app.providers.llm.time.sleep", return_value=None),
            pytest.raises(ServiceUnavailableError) as exc_info,
        ):
            provider.complete(_request())
        assert exc_info.value.details["reason"] == "openai_llm_rate_limited"

    def test_timeout(self) -> None:
        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            fail_closed=True,
        )
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.post.side_effect = httpx.ReadTimeout("timed out")
        with (
            patch("httpx.Client", return_value=client),
            patch("app.providers.llm.time.sleep", return_value=None),
            pytest.raises(ServiceUnavailableError) as exc_info,
        ):
            provider.complete(_request())
        assert exc_info.value.details["reason"] == "openai_llm_timeout"

    def test_malformed_response_empty_output(self) -> None:
        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            fail_closed=True,
        )
        response = _http_response(payload={"model": "gpt-5.6-sol", "output": [], "usage": {}})
        with (
            patch("httpx.Client", return_value=_mock_client_with_response(response)),
            pytest.raises(ServiceUnavailableError) as exc_info,
        ):
            provider.complete(_request())
        assert exc_info.value.details["reason"] == "openai_llm_malformed_response"


class TestGenerationReadiness:
    def test_status_unhealthy_when_listing_ok_but_generation_fails(self) -> None:
        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            fail_closed=True,
            generation_probe_ttl_seconds=0.0,
        )

        list_response = _http_response(
            status_code=200,
            payload={"data": [{"id": "gpt-5.6-sol"}]},
        )
        gen_response = _http_response(
            status_code=400,
            payload={"error": {"code": "unsupported_parameter", "type": "invalid_request_error"}},
        )

        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.get.return_value = list_response
        client.post.return_value = gen_response

        with patch("httpx.Client", return_value=client):
            status = provider.status()
        assert status.health == ProviderHealth.UNAVAILABLE
        assert status.using_fallback is False
        assert (
            "listing OK" in (status.detail or "")
            or "generation unavailable" in (status.detail or "").lower()
        )

    def test_status_healthy_when_generation_succeeds(self) -> None:
        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            fail_closed=True,
            generation_probe_ttl_seconds=0.0,
        )
        list_response = _http_response(
            status_code=200,
            payload={"data": [{"id": "gpt-5.6-sol"}]},
        )
        gen_response = _http_response(
            payload={"output_text": "OK", "model": "gpt-5.6-sol", "usage": {}}
        )
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.get.return_value = list_response
        client.post.return_value = gen_response
        with patch("httpx.Client", return_value=client):
            status = provider.status()
        assert status.health == ProviderHealth.HEALTHY
        assert "generation ready" in (status.detail or "").lower()
        assert "responses" in (status.detail or "").lower()

    def test_classic_model_still_uses_chat_completions(self) -> None:
        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            fail_closed=True,
        )
        response = _http_response(
            payload={
                "model": "gpt-4o-mini",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
        )
        client = _mock_client_with_response(response)
        with patch("httpx.Client", return_value=client):
            result = provider.complete(_request(model="gpt-4o-mini"))
        assert result.content == "ok"
        assert client.post.call_args.args[0].endswith("/chat/completions")

    def test_generation_probe_uses_cheap_responses_settings(self) -> None:
        from app.providers import llm as llm_mod

        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            fail_closed=True,
            generation_probe_ttl_seconds=0.0,
        )
        list_response = _http_response(
            status_code=200,
            payload={"data": [{"id": "gpt-5.6-sol"}]},
        )
        gen_response = _http_response(
            payload={"output_text": "OK", "model": "gpt-5.6-sol", "usage": {}}
        )
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.get.return_value = list_response
        client.post.return_value = gen_response
        with patch("httpx.Client", return_value=client):
            provider.status()
        body = client.post.call_args.kwargs["json"]
        assert client.post.call_args.args[0].endswith("/responses")
        assert body["max_output_tokens"] == llm_mod._GENERATION_PROBE_MAX_OUTPUT_TOKENS
        assert body["reasoning"]["effort"] == "none"
        assert body["input"][0]["content"] == llm_mod._GENERATION_PROBE_PROMPT
        assert body["store"] is False

    def test_generation_probe_cache_avoids_repeat_calls(self) -> None:
        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            fail_closed=True,
            generation_probe_ttl_seconds=300.0,
        )
        list_response = _http_response(
            status_code=200,
            payload={"data": [{"id": "gpt-5.6-sol"}]},
        )
        gen_response = _http_response(
            payload={"output_text": "OK", "model": "gpt-5.6-sol", "usage": {}}
        )
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.get.return_value = list_response
        client.post.return_value = gen_response
        with patch("httpx.Client", return_value=client):
            assert provider.status().health == ProviderHealth.HEALTHY
            assert provider.status().health == ProviderHealth.HEALTHY
        assert client.post.call_count == 1

    def test_concurrent_status_coalesces_to_single_probe(self) -> None:
        import threading

        provider = OpenAILLMProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            model="gpt-5.6-sol",
            fail_closed=True,
            generation_probe_ttl_seconds=300.0,
        )
        list_response = _http_response(
            status_code=200,
            payload={"data": [{"id": "gpt-5.6-sol"}]},
        )
        gen_response = _http_response(
            payload={"output_text": "OK", "model": "gpt-5.6-sol", "usage": {}}
        )
        started = threading.Event()
        release = threading.Event()

        def _post(*_a: Any, **_k: Any) -> MagicMock:
            started.set()
            assert release.wait(timeout=2.0)
            return gen_response

        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.get.return_value = list_response
        client.post.side_effect = _post

        results: list[ProviderHealth] = []
        errors: list[BaseException] = []

        def _worker() -> None:
            try:
                results.append(provider.status().health)
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(4)]
        with patch("httpx.Client", return_value=client):
            for t in threads:
                t.start()
            assert started.wait(timeout=2.0)
            release.set()
            for t in threads:
                t.join(timeout=3.0)
        assert not errors
        assert results == [ProviderHealth.HEALTHY] * 4
        assert client.post.call_count == 1
