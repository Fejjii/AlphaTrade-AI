"""Embedding dimension resolution and provider alignment tests."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings
from app.providers.embedding_dimensions import (
    MOCK_EMBEDDINGS_DIMENSIONS,
    model_supports_dimensions_param,
    resolve_embeddings_dimensions,
)
from app.providers.embeddings import MockEmbeddingsProvider, OpenAIEmbeddingsProvider
from app.providers.factory import resolve_providers


def test_mock_default_dimensions() -> None:
    settings = Settings(openai_api_key="", log_json=False)
    assert resolve_embeddings_dimensions(settings) == MOCK_EMBEDDINGS_DIMENSIONS
    resolved = resolve_providers(settings)
    assert resolved.embeddings_dimensions == MOCK_EMBEDDINGS_DIMENSIONS
    assert len(resolved.embeddings.embed(["x"])[0]) == MOCK_EMBEDDINGS_DIMENSIONS


def test_openai_key_selects_model_native_dimensions() -> None:
    settings = Settings(
        openai_api_key="sk-test",
        embeddings_model="text-embedding-3-small",
        log_json=False,
        qdrant_url="",
        provider_mode="fallback",
    )
    assert resolve_embeddings_dimensions(settings) == 1536
    resolved = resolve_providers(settings)
    assert resolved.embeddings.name == "openai-embeddings"
    assert resolved.embeddings.dimensions == 1536


def test_explicit_embeddings_dimensions_override() -> None:
    settings = Settings(
        openai_api_key="sk-test",
        embeddings_model="text-embedding-3-small",
        embeddings_dimensions=512,
        log_json=False,
    )
    assert resolve_embeddings_dimensions(settings) == 512


def test_openai_fallback_mock_matches_dimensions() -> None:
    provider = OpenAIEmbeddingsProvider(
        model="text-embedding-3-small",
        api_key="",
        base_url="https://api.openai.com/v1",
        dimensions=1536,
    )
    result = provider.embed_with_metadata(["alpha"])
    assert result.fallback_used is True
    assert result.dimensions == 1536
    assert len(result.vectors[0]) == 1536


def test_openai_request_includes_dimensions_for_v3_models(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "model": "text-embedding-3-small",
                "data": [{"index": 0, "embedding": [0.1] * 512}],
                "usage": {"prompt_tokens": 3},
            }

    class _Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, headers: dict[str, str], json: dict[str, object]) -> _Resp:
            captured["url"] = url
            captured["json"] = json
            return _Resp()

    monkeypatch.setattr(httpx, "Client", _Client)
    provider = OpenAIEmbeddingsProvider(
        model="text-embedding-3-small",
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        dimensions=512,
    )
    result = provider.embed_with_metadata(["hello"])
    assert result.fallback_used is False
    assert captured["json"] == {
        "model": "text-embedding-3-small",
        "input": ["hello"],
        "dimensions": 512,
    }
    assert len(result.vectors[0]) == 512


def test_openai_dimension_mismatch_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "model": "text-embedding-3-small",
                "data": [{"index": 0, "embedding": [0.1] * 8}],
                "usage": {"prompt_tokens": 1},
            }

    class _Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, *args: object, **kwargs: object) -> _Resp:
            return _Resp()

    monkeypatch.setattr(httpx, "Client", _Client)
    provider = OpenAIEmbeddingsProvider(
        model="text-embedding-3-small",
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        dimensions=1536,
    )
    result = provider.embed_with_metadata(["hello"])
    assert result.fallback_used is True
    assert len(result.vectors[0]) == 1536


def test_model_supports_dimensions_param() -> None:
    assert model_supports_dimensions_param("text-embedding-3-small") is True
    assert model_supports_dimensions_param("text-embedding-ada-002") is False


def test_mock_provider_rejects_invalid_dimensions() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        MockEmbeddingsProvider(dimensions=0)


def test_fallback_dimensions_must_align() -> None:
    with pytest.raises(ValueError, match="fallback dimensions"):
        OpenAIEmbeddingsProvider(
            model="text-embedding-3-small",
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            dimensions=1536,
            fallback=MockEmbeddingsProvider(dimensions=384),
        )


def test_embedding_result_serializes_dimensions() -> None:
    result = MockEmbeddingsProvider(dimensions=8).embed_with_metadata(["z"])
    payload = json.loads(
        json.dumps(
            {
                "dimensions": result.dimensions,
                "provider": result.provider,
                "fallback_used": result.fallback_used,
            }
        )
    )
    assert payload["dimensions"] == 8
