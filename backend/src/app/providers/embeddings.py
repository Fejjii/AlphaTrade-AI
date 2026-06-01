"""Embedding provider abstraction for RAG."""

from __future__ import annotations

import hashlib
import math
import struct
import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import httpx
import structlog

from app.providers.base import BaseMockProvider, ProviderHealth, ProviderKind, ProviderStatus

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    provider: str
    input_tokens: int = 0
    latency_ms: float = 0.0
    fallback_used: bool = False


@runtime_checkable
class EmbeddingsProvider(Protocol):
    """Generate vector embeddings for retrieval."""

    name: str
    kind: ProviderKind

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...

    def embed_with_metadata(self, texts: list[str]) -> EmbeddingResult:
        """Return embeddings plus usage metadata when available."""
        ...

    def status(self) -> ProviderStatus: ...


def _deterministic_vector(text: str, *, dimensions: int = 384) -> list[float]:
    """Hash text into a stable unit-length vector for mock retrieval."""
    digest = hashlib.sha256(text.encode()).digest()
    values: list[float] = []
    counter = 0
    while len(values) < dimensions:
        block = hashlib.sha256(digest + struct.pack(">I", counter)).digest()
        counter += 1
        for i in range(0, len(block), 4):
            if len(values) >= dimensions:
                break
            raw = struct.unpack(">I", block[i : i + 4])[0]
            values.append((raw / 2**32) * 2 - 1)
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


class MockEmbeddingsProvider(BaseMockProvider):
    """Deterministic embeddings for offline tests and local development."""

    def __init__(self, *, dimensions: int = 384) -> None:
        super().__init__(
            "mock-embeddings",
            ProviderKind.EMBEDDINGS,
            detail="Deterministic hash-based embeddings for tests.",
        )
        self._dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.embed_with_metadata(texts).vectors

    def embed_with_metadata(self, texts: list[str]) -> EmbeddingResult:
        vectors = [_deterministic_vector(text, dimensions=self._dimensions) for text in texts]
        return EmbeddingResult(
            vectors=vectors,
            model="mock-embeddings",
            provider=self.name,
            input_tokens=max(sum(len(t) for t in texts) // 4, len(texts)),
            latency_ms=1.0,
            fallback_used=True,
        )


class OpenAIEmbeddingsProvider:
    """OpenAI-compatible embeddings via HTTP with mock fallback."""

    name = "openai-embeddings"
    kind = ProviderKind.EMBEDDINGS

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        fallback: MockEmbeddingsProvider | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._fallback = fallback or MockEmbeddingsProvider()
        self._timeout = timeout_seconds

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.embed_with_metadata(texts).vectors

    def embed_with_metadata(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                vectors=[],
                model=self._model,
                provider=self.name,
            )
        if not self._api_key:
            result = self._fallback.embed_with_metadata(texts)
            return EmbeddingResult(
                vectors=result.vectors,
                model=self._model,
                provider=self.name,
                input_tokens=result.input_tokens,
                latency_ms=result.latency_ms,
                fallback_used=True,
            )

        started = time.perf_counter()
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self._base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self._model, "input": texts},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            logger.warning("openai_embeddings_fallback", error=str(exc))
            result = self._fallback.embed_with_metadata(texts)
            return EmbeddingResult(
                vectors=result.vectors,
                model=self._model,
                provider=self.name,
                input_tokens=result.input_tokens,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                fallback_used=True,
            )

        data = payload.get("data") or []
        ordered = sorted(data, key=lambda row: row.get("index", 0))
        vectors = [list(row["embedding"]) for row in ordered]
        usage = payload.get("usage") or {}
        return EmbeddingResult(
            vectors=vectors,
            model=str(payload.get("model") or self._model),
            provider=self.name,
            input_tokens=int(usage.get("prompt_tokens") or usage.get("total_tokens") or 0),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            fallback_used=False,
        )

    def status(self) -> ProviderStatus:
        if not self._api_key:
            return ProviderStatus(
                name=self.name,
                kind=self.kind,
                health=ProviderHealth.UNAVAILABLE,
                using_fallback=True,
                is_mock=False,
                detail="OPENAI_API_KEY not configured — using mock-embeddings fallback.",
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
                        detail=f"OpenAI-compatible embeddings ({self._model}).",
                    )
        except Exception as exc:
            logger.debug("openai_embeddings_status_degraded", error=str(exc))
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=ProviderHealth.DEGRADED,
            using_fallback=True,
            is_mock=False,
            detail="OpenAI embeddings API unreachable — mock fallback active at runtime.",
        )
