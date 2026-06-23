"""Vector store abstraction for Qdrant-backed retrieval."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

import structlog

from app.providers.base import BaseMockProvider, ProviderHealth, ProviderKind, ProviderStatus

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class VectorPoint:
    """A vector point to upsert into the store."""

    point_id: str
    vector: list[float]
    payload: dict[str, Any]


@dataclass(frozen=True)
class VectorSearchHit:
    """A scored vector search result."""

    point_id: str
    score: float
    payload: dict[str, Any]


@dataclass(frozen=True)
class VectorSearchFilters:
    organization_id: UUID | None = None
    user_id: UUID | None = None
    source_types: tuple[str, ...] = ()
    strategy_tag: str | None = None
    symbol_tag: str | None = None
    timeframe_tag: str | None = None
    risk_tag: str | None = None


@runtime_checkable
class VectorStore(Protocol):
    """Minimal Qdrant-like interface used by RagService."""

    name: str

    def upsert(self, collection: str, points: list[VectorPoint]) -> None: ...

    def search(
        self,
        collection: str,
        vector: list[float],
        *,
        filters: VectorSearchFilters,
        top_k: int,
    ) -> list[VectorSearchHit]: ...

    def status(self) -> ProviderStatus: ...


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
    return max(min(dot / (norm_a * norm_b), 1.0), -1.0)


def _normalize_score(raw: float) -> float:
    """Map cosine similarity [-1, 1] to [0, 1]."""
    return (raw + 1.0) / 2.0


def _matches_filters(payload: dict[str, Any], filters: VectorSearchFilters) -> bool:
    if filters.organization_id is not None and payload.get("organization_id") != str(
        filters.organization_id
    ):
        return False
    if filters.user_id is not None and payload.get("user_id") != str(filters.user_id):
        return False
    if filters.source_types and payload.get("source_type") not in filters.source_types:
        return False
    if filters.strategy_tag is not None and payload.get("strategy_tag") != filters.strategy_tag:
        return False
    if filters.symbol_tag is not None and payload.get("symbol_tag") != filters.symbol_tag:
        return False
    if filters.timeframe_tag is not None and payload.get("timeframe_tag") != filters.timeframe_tag:
        return False
    return not (filters.risk_tag is not None and payload.get("risk_tag") != filters.risk_tag)


@dataclass
class InMemoryVectorStore:
    """Deterministic in-memory vector store for tests and offline use."""

    name: str = "in-memory-vector"

    _collections: dict[str, dict[str, VectorPoint]] = field(default_factory=dict)

    def clear(self) -> None:
        self._collections.clear()

    def upsert(self, collection: str, points: list[VectorPoint]) -> None:
        bucket = self._collections.setdefault(collection, {})
        for point in points:
            bucket[point.point_id] = point

    def search(
        self,
        collection: str,
        vector: list[float],
        *,
        filters: VectorSearchFilters,
        top_k: int,
    ) -> list[VectorSearchHit]:
        bucket = self._collections.get(collection, {})
        hits: list[VectorSearchHit] = []
        for point in bucket.values():
            if not _matches_filters(point.payload, filters):
                continue
            raw = _cosine_similarity(vector, point.vector)
            hits.append(
                VectorSearchHit(
                    point_id=point.point_id,
                    score=_normalize_score(raw),
                    payload=point.payload,
                )
            )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            kind=ProviderKind.VECTOR,
            health=ProviderHealth.HEALTHY,
            using_fallback=True,
            is_mock=True,
            detail="In-memory vector store for deterministic tests and offline mode.",
        )


class MockQdrantProvider(BaseMockProvider):
    """Provider wrapper exposing in-memory vector store health."""

    def __init__(self, store: InMemoryVectorStore | None = None) -> None:
        super().__init__(
            "qdrant-mock",
            ProviderKind.VECTOR,
            detail="Mock Qdrant via in-memory vector store.",
        )
        self.store = store or InMemoryVectorStore()


def _build_qdrant_filter(filters: VectorSearchFilters) -> dict[str, Any] | None:
    must: list[dict[str, Any]] = []
    if filters.organization_id is not None:
        must.append(
            {
                "key": "organization_id",
                "match": {"value": str(filters.organization_id)},
            }
        )
    if filters.user_id is not None:
        must.append({"key": "user_id", "match": {"value": str(filters.user_id)}})
    if filters.source_types:
        must.append({"key": "source_type", "match": {"any": list(filters.source_types)}})
    if filters.strategy_tag is not None:
        must.append({"key": "strategy_tag", "match": {"value": filters.strategy_tag}})
    if filters.symbol_tag is not None:
        must.append({"key": "symbol_tag", "match": {"value": filters.symbol_tag}})
    if filters.timeframe_tag is not None:
        must.append({"key": "timeframe_tag", "match": {"value": filters.timeframe_tag}})
    if filters.risk_tag is not None:
        must.append({"key": "risk_tag", "match": {"value": filters.risk_tag}})
    if not must:
        return None
    return {"must": must}


class QdrantVectorStore:
    """Real Qdrant client with in-memory fallback on failure."""

    name = "qdrant"

    def __init__(
        self,
        url: str,
        *,
        fallback: InMemoryVectorStore | None = None,
        vector_size: int = 384,
    ) -> None:
        self._url = url
        self._fallback = fallback or InMemoryVectorStore()
        self._vector_size = vector_size
        self._client = None
        self._using_qdrant = False
        self._connect()

    def _connect(self) -> None:
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(url=self._url, timeout=5.0)
            client.get_collections()
            self._client = client
            self._using_qdrant = True
        except Exception as exc:
            logger.warning("qdrant_connect_failed", url=self._url, error=str(exc))
            self._client = None
            self._using_qdrant = False

    def _ensure_collection(self, collection: str, *, vector_size: int | None = None) -> None:
        if self._client is None:
            return
        from qdrant_client.http import models as qmodels

        size = vector_size or self._vector_size
        try:
            self._client.get_collection(collection)
        except Exception:
            self._client.create_collection(
                collection_name=collection,
                vectors_config=qmodels.VectorParams(size=size, distance=qmodels.Distance.COSINE),
            )

    def upsert(self, collection: str, points: list[VectorPoint]) -> None:
        if not points:
            return
        vector_size = len(points[0].vector)
        if not self._using_qdrant or self._client is None:
            self._fallback.upsert(collection, points)
            return
        try:
            from qdrant_client.http import models as qmodels

            self._ensure_collection(collection, vector_size=vector_size)
            qdrant_points = [
                qmodels.PointStruct(
                    id=_point_id_to_uuid(point.point_id),
                    vector=point.vector,
                    payload=point.payload,
                )
                for point in points
            ]
            self._client.upsert(collection_name=collection, points=qdrant_points)
        except Exception as exc:
            logger.warning("qdrant_upsert_fallback", error=str(exc))
            self._fallback.upsert(collection, points)

    def search(
        self,
        collection: str,
        vector: list[float],
        *,
        filters: VectorSearchFilters,
        top_k: int,
    ) -> list[VectorSearchHit]:
        if not self._using_qdrant or self._client is None:
            return self._fallback.search(collection, vector, filters=filters, top_k=top_k)
        try:
            from qdrant_client.http import models as qmodels

            self._ensure_collection(collection, vector_size=len(vector))
            q_filter = _build_qdrant_filter(filters)
            query_filter = qmodels.Filter.model_validate(q_filter) if q_filter else None
            results = self._client.search(
                collection_name=collection,
                query_vector=vector,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
            )
            hits: list[VectorSearchHit] = []
            for row in results:
                point_id = str(row.id)
                payload = dict(row.payload or {})
                if "chunk_id" in payload:
                    point_id = str(payload["chunk_id"])
                hits.append(
                    VectorSearchHit(
                        point_id=point_id,
                        score=float(row.score),
                        payload=payload,
                    )
                )
            return hits
        except Exception as exc:
            logger.warning("qdrant_search_fallback", error=str(exc))
            return self._fallback.search(collection, vector, filters=filters, top_k=top_k)

    def status(self) -> ProviderStatus:
        # The hosted Qdrant URL is intentionally omitted from `detail`: this
        # status is served publicly via the unauthenticated /providers/status
        # endpoint. The endpoint is logged server-side at connect time instead.
        if self._using_qdrant:
            return ProviderStatus(
                name=self.name,
                kind=ProviderKind.VECTOR,
                health=ProviderHealth.HEALTHY,
                using_fallback=False,
                is_mock=False,
                detail="Qdrant connected.",
            )
        return ProviderStatus(
            name=self.name,
            kind=ProviderKind.VECTOR,
            health=ProviderHealth.DEGRADED,
            using_fallback=True,
            is_mock=True,
            detail="Qdrant unavailable — in-memory vector fallback active.",
        )


def _point_id_to_uuid(point_id: str) -> str:
    try:
        return str(uuid.UUID(point_id))
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, point_id))


_process_vector_store: InMemoryVectorStore | None = None


def get_process_vector_store() -> InMemoryVectorStore:
    """Shared in-process vector store until real Qdrant is wired."""
    global _process_vector_store
    if _process_vector_store is None:
        _process_vector_store = InMemoryVectorStore()
    return _process_vector_store


def reset_process_vector_store() -> None:
    """Reset shared store — for deterministic tests."""
    global _process_vector_store
    _process_vector_store = None
