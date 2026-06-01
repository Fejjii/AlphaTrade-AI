"""RAG ingestion and retrieval service — sole boundary for knowledge base access."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Chunk as ChunkModel
from app.db.models import Document as DocumentModel
from app.providers.embeddings import EmbeddingsProvider, MockEmbeddingsProvider
from app.providers.factory import resolve_providers
from app.providers.qdrant import (
    InMemoryVectorStore,
    VectorPoint,
    VectorSearchFilters,
    VectorStore,
)
from app.rag.text_processing import (
    chunk_text,
    compute_source_hash,
    compute_text_hash,
    estimate_token_count,
    stable_chunk_id,
)
from app.repositories.chunks import ChunkRepository
from app.repositories.documents import DocumentRepository
from app.schemas.common import DocumentSourceType
from app.schemas.rag import (
    ChunkMetadata,
    Citation,
    DocumentCreateRequest,
    IngestDocumentRequest,
    IngestDocumentResponse,
    RagChunk,
    RagDocument,
    RagQuery,
    RagSearchResponse,
    RetrievedChunk,
)
from app.schemas.usage import UsageEventCreate
from app.services.audit_service import AuditService
from app.services.usage_service import UsageService

logger = structlog.get_logger(__name__)

RAG_COLLECTION = "alphatrade_knowledge"


class RagService:
    """Ingest documents and retrieve grounded context with citations.

    RAG provides rules, explanations, and journal lessons only — never direct
    trading signals or order instructions.
    """

    def __init__(
        self,
        session: Session | None = None,
        *,
        embeddings: EmbeddingsProvider | None = None,
        vector_store: VectorStore | None = None,
        audit_service: AuditService | None = None,
        usage_service: UsageService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._embeddings = embeddings or MockEmbeddingsProvider()
        self._vector_store = vector_store or InMemoryVectorStore()
        self._documents = DocumentRepository(session) if session is not None else None
        self._chunks = ChunkRepository(session) if session is not None else None
        self._audit = audit_service or AuditService()
        self._usage = usage_service or UsageService()

    def create_document(self, data: DocumentCreateRequest) -> RagDocument:
        """Register document metadata without body ingestion."""
        if self._documents is None:
            raise RuntimeError("Database session required to create documents.")
        now = datetime.now(UTC)
        entity = DocumentModel(
            id=uuid.uuid4(),
            organization_id=data.organization_id,
            user_id=data.user_id,
            source_type=data.source_type,
            title=data.title,
            uri=data.source_uri,
            version=data.version,
            source_hash=None,
            tags=[],
            created_at=now,
            updated_at=now,
        )
        self._documents.add(entity)
        self._session.commit()
        return _document_to_schema(entity)

    def ingest(self, data: IngestDocumentRequest) -> IngestDocumentResponse:
        """Normalize, chunk, embed, and persist a text document."""
        if self._documents is None or self._chunks is None:
            raise RuntimeError("Database session required for ingestion.")

        source_hash = compute_source_hash(
            title=data.title,
            text=data.text,
            source_type=data.source_type.value,
            organization_id=data.organization_id,
        )
        existing = self._documents.get_by_source_hash(
            organization_id=data.organization_id,
            source_hash=source_hash,
        )
        if existing is not None:
            chunk_count = len(self._chunks.list_by_document(existing.id))
            return IngestDocumentResponse(
                document_id=existing.id,
                source_hash=source_hash,
                chunk_count=chunk_count,
                duplicate=True,
                version=existing.version,
            )

        now = datetime.now(UTC)
        document_id = uuid.uuid4()
        document = DocumentModel(
            id=document_id,
            organization_id=data.organization_id,
            user_id=data.user_id,
            source_type=data.source_type,
            title=data.title,
            uri=data.source_uri,
            source_hash=source_hash,
            version=data.version,
            tags=[],
            created_at=now,
            updated_at=now,
        )
        self._documents.add(document)

        text_chunks = chunk_text(data.text)
        embed_result = self._embeddings.embed_with_metadata(text_chunks)
        vectors = embed_result.vectors
        self._record_embedding_usage(
            organization_id=data.organization_id,
            user_id=data.user_id,
            text_count=len(text_chunks),
            feature="rag_ingest",
            provider=embed_result.provider,
            input_tokens=embed_result.input_tokens,
            fallback_used=embed_result.fallback_used,
            latency_ms=embed_result.latency_ms,
        )

        vector_points: list[VectorPoint] = []
        for ordinal, (content, vector) in enumerate(zip(text_chunks, vectors, strict=True)):
            text_hash = compute_text_hash(content)
            chunk_id = stable_chunk_id(document_id, ordinal, text_hash)
            metadata = ChunkMetadata(
                title=data.title,
                section_title=_infer_section_title(content),
                source_type=data.source_type,
                strategy_tag=data.strategy_tag,
                symbol_tag=data.symbol_tag,
                timeframe_tag=data.timeframe_tag,
                risk_tag=data.risk_tag,
            )
            chunk = ChunkModel(
                id=chunk_id,
                document_id=document_id,
                organization_id=data.organization_id,
                user_id=data.user_id,
                ordinal=ordinal,
                content=content,
                token_count=estimate_token_count(content),
                text_hash=text_hash,
                embedding_ref=str(chunk_id),
                chunk_metadata=metadata.model_dump(mode="json"),
                created_at=now,
                updated_at=now,
            )
            self._chunks.add(chunk)
            vector_points.append(
                VectorPoint(
                    point_id=str(chunk_id),
                    vector=vector,
                    payload=_vector_payload(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        organization_id=data.organization_id,
                        user_id=data.user_id,
                        metadata=metadata,
                    ),
                )
            )

        self._vector_store.upsert(RAG_COLLECTION, vector_points)
        self._session.commit()
        logger.info(
            "rag_ingest_complete",
            document_id=str(document_id),
            chunk_count=len(text_chunks),
            source_type=data.source_type.value,
        )
        return IngestDocumentResponse(
            document_id=document_id,
            source_hash=source_hash,
            chunk_count=len(text_chunks),
            duplicate=False,
            version=data.version,
        )

    def upsert_linked_document(self, data: IngestDocumentRequest) -> IngestDocumentResponse:
        """Ingest or replace chunks for a stable ``source_uri`` (e.g. journal entries)."""
        if self._documents is None or self._chunks is None:
            raise RuntimeError("Database session required for ingestion.")
        if not data.source_uri:
            return self.ingest(data)

        source_hash = compute_source_hash(
            title=data.title,
            text=data.text,
            source_type=data.source_type.value,
            organization_id=data.organization_id,
        )
        existing = self._documents.get_by_source_uri(
            organization_id=data.organization_id,
            source_uri=data.source_uri,
        )
        if existing is not None and existing.source_hash == source_hash:
            chunk_count = len(self._chunks.list_by_document(existing.id))
            return IngestDocumentResponse(
                document_id=existing.id,
                source_hash=source_hash,
                chunk_count=chunk_count,
                duplicate=True,
                version=existing.version,
            )

        if existing is not None:
            for chunk in self._chunks.list_by_document(existing.id):
                self._session.delete(chunk)
            existing.title = data.title
            existing.source_hash = source_hash
            existing.version = existing.version + 1
            existing.updated_at = datetime.now(UTC)
            self._documents.add(existing)
            return self._ingest_into_document(existing.id, data, source_hash=source_hash)

        return self.ingest(data)

    def _ingest_into_document(
        self,
        document_id: uuid.UUID,
        data: IngestDocumentRequest,
        *,
        source_hash: str,
    ) -> IngestDocumentResponse:
        """Chunk, embed, and persist text into an existing document row."""
        if self._documents is None or self._chunks is None:
            raise RuntimeError("Database session required for ingestion.")

        now = datetime.now(UTC)
        text_chunks = chunk_text(data.text)
        embed_result = self._embeddings.embed_with_metadata(text_chunks)
        vectors = embed_result.vectors
        self._record_embedding_usage(
            organization_id=data.organization_id,
            user_id=data.user_id,
            text_count=len(text_chunks),
            feature="rag_ingest",
            provider=embed_result.provider,
            input_tokens=embed_result.input_tokens,
            fallback_used=embed_result.fallback_used,
            latency_ms=embed_result.latency_ms,
        )

        vector_points: list[VectorPoint] = []
        for ordinal, (content, vector) in enumerate(zip(text_chunks, vectors, strict=True)):
            text_hash = compute_text_hash(content)
            chunk_id = stable_chunk_id(document_id, ordinal, text_hash)
            metadata = ChunkMetadata(
                title=data.title,
                section_title=_infer_section_title(content),
                source_type=data.source_type,
                strategy_tag=data.strategy_tag,
                symbol_tag=data.symbol_tag,
                timeframe_tag=data.timeframe_tag,
                risk_tag=data.risk_tag,
            )
            chunk = ChunkModel(
                id=chunk_id,
                document_id=document_id,
                organization_id=data.organization_id,
                user_id=data.user_id,
                ordinal=ordinal,
                content=content,
                token_count=estimate_token_count(content),
                text_hash=text_hash,
                embedding_ref=str(chunk_id),
                chunk_metadata=metadata.model_dump(mode="json"),
                created_at=now,
                updated_at=now,
            )
            self._chunks.add(chunk)
            vector_points.append(
                VectorPoint(
                    point_id=str(chunk_id),
                    vector=vector,
                    payload=_vector_payload(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        organization_id=data.organization_id,
                        user_id=data.user_id,
                        metadata=metadata,
                    ),
                )
            )

        self._vector_store.upsert(RAG_COLLECTION, vector_points)
        self._session.commit()
        document = self._documents.get(document_id)
        version = document.version if document is not None else data.version
        return IngestDocumentResponse(
            document_id=document_id,
            source_hash=source_hash,
            chunk_count=len(text_chunks),
            duplicate=False,
            version=version,
        )

    def search(self, query: RagQuery, *, request_id: str | None = None) -> RagSearchResponse:
        """Retrieve ranked chunks with citation metadata."""
        embed_result = self._embeddings.embed_with_metadata([query.query])
        vectors = embed_result.vectors
        self._record_embedding_usage(
            organization_id=query.organization_id,
            user_id=query.user_id,
            text_count=1,
            feature="rag_search",
            request_id=request_id,
            provider=embed_result.provider,
            input_tokens=embed_result.input_tokens,
            fallback_used=embed_result.fallback_used,
            latency_ms=embed_result.latency_ms,
        )
        filters = VectorSearchFilters(
            organization_id=query.organization_id,
            user_id=query.user_id,
            source_types=tuple(st.value for st in query.source_types),
            strategy_tag=query.strategy_tag,
            symbol_tag=query.symbol_tag,
            timeframe_tag=query.timeframe_tag,
            risk_tag=query.risk_tag,
        )
        hits = self._vector_store.search(
            RAG_COLLECTION,
            vectors[0],
            filters=filters,
            top_k=query.top_k,
        )

        chunk_ids = [UUID(hit.point_id) for hit in hits]
        chunk_map: dict[UUID, ChunkModel] = {}
        if self._chunks is not None and chunk_ids:
            for chunk in self._chunks.get_many(chunk_ids):
                chunk_map[chunk.id] = chunk

        retrieved: list[RetrievedChunk] = []
        citations: list[Citation] = []
        for hit in hits:
            chunk_id = UUID(hit.point_id)
            chunk = chunk_map.get(chunk_id)
            if chunk is None:
                continue
            metadata = _chunk_metadata_from_row(chunk)
            retrieved.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    title=metadata.title,
                    section_title=metadata.section_title,
                    page_number=metadata.page_number,
                    chunk_ordinal=chunk.ordinal,
                    source_type=metadata.source_type,
                    content=chunk.content,
                    score=hit.score,
                )
            )
            citations.append(_citation_from_chunk(chunk, metadata, score=hit.score))

        return RagSearchResponse(query=query.query, chunks=retrieved, citations=citations)

    def retrieve_for_agent(
        self,
        *,
        query: str,
        organization_id: UUID | None,
        user_id: UUID | None,
        request_id: str | None = None,
        top_k: int = 5,
    ) -> RagSearchResponse:
        """Scoped retrieval for agent context — rules and lessons only."""
        return self.search(
            RagQuery(
                query=query,
                organization_id=organization_id,
                user_id=user_id,
                top_k=top_k,
                source_types=[
                    DocumentSourceType.TRADING_PLAYBOOK,
                    DocumentSourceType.RISK_POLICY,
                    DocumentSourceType.TRADE_JOURNAL,
                    DocumentSourceType.REVIEW_NOTE,
                    DocumentSourceType.MISTAKES_DATABASE,
                    DocumentSourceType.GENERAL_NOTE,
                ],
            ),
            request_id=request_id,
        )

    def list_documents(
        self,
        *,
        organization_id: UUID | None = None,
        user_id: UUID | None = None,
        source_type: DocumentSourceType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RagDocument], int]:
        if self._documents is None:
            return [], 0
        rows, total = self._documents.list_documents(
            organization_id=organization_id,
            user_id=user_id,
            source_type=source_type,
            limit=limit,
            offset=offset,
        )
        return [_document_to_schema(row) for row in rows], total

    def list_chunks(
        self,
        *,
        document_id: UUID | None = None,
        organization_id: UUID | None = None,
        user_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RagChunk], int]:
        if self._chunks is None:
            return [], 0
        rows, total = self._chunks.list_chunks(
            document_id=document_id,
            organization_id=organization_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        return [_chunk_to_schema(row) for row in rows], total

    def _record_embedding_usage(
        self,
        *,
        organization_id: UUID | None,
        user_id: UUID | None,
        text_count: int,
        feature: str,
        request_id: str | None = None,
        provider: str | None = None,
        input_tokens: int | None = None,
        fallback_used: bool = False,
        latency_ms: float | None = None,
    ) -> None:
        from app.schemas.common import CostSource
        from app.services.usage_cost import build_provider_metadata

        resolved_input = input_tokens if input_tokens is not None else max(text_count * 32, 1)
        self._usage.record(
            UsageEventCreate(
                request_id=request_id or "rag-local",
                organization_id=organization_id,
                user_id=user_id,
                feature=feature,
                model=self._settings.embeddings_model,
                provider=provider or self._embeddings.name,
                input_tokens=resolved_input,
                output_tokens=0,
                fallback_used=fallback_used,
                latency_ms=latency_ms,
                provider_metadata=build_provider_metadata(
                    input_tokens=resolved_input,
                    output_tokens=0,
                    cost_source=(
                        CostSource.TOKENIZER_ESTIMATED
                        if resolved_input and not fallback_used
                        else CostSource.STATIC_ESTIMATED
                    ),
                    fallback_used=fallback_used,
                    embedding_calls=text_count,
                ),
            )
        )


def build_rag_service(
    settings: Settings | None = None,
    session: Session | None = None,
    *,
    vector_store: VectorStore | None = None,
    embeddings: EmbeddingsProvider | None = None,
    audit_service: AuditService | None = None,
    usage_service: UsageService | None = None,
) -> RagService:
    """Factory used by API and agent runtime wiring."""
    settings = settings or get_settings()
    resolved = resolve_providers(settings)
    return RagService(
        session,
        settings=settings,
        embeddings=embeddings or resolved.embeddings,
        vector_store=vector_store or resolved.vector_store,
        audit_service=audit_service,
        usage_service=usage_service,
    )


def _infer_section_title(content: str) -> str | None:
    first_line = content.split("\n", 1)[0].strip()
    if first_line.endswith(":") or (first_line.isupper() and len(first_line) < 80):
        return first_line.rstrip(":")
    return None


def _vector_payload(
    *,
    chunk_id: UUID,
    document_id: UUID,
    organization_id: UUID | None,
    user_id: UUID | None,
    metadata: ChunkMetadata,
) -> dict[str, Any]:
    return {
        "chunk_id": str(chunk_id),
        "document_id": str(document_id),
        "organization_id": str(organization_id) if organization_id else None,
        "user_id": str(user_id) if user_id else None,
        "source_type": metadata.source_type.value,
        "strategy_tag": metadata.strategy_tag,
        "symbol_tag": metadata.symbol_tag,
        "timeframe_tag": metadata.timeframe_tag,
        "risk_tag": metadata.risk_tag,
    }


def _document_to_schema(entity: DocumentModel) -> RagDocument:
    return RagDocument(
        id=entity.id,
        organization_id=entity.organization_id,
        user_id=entity.user_id,
        source_type=entity.source_type,
        title=entity.title,
        source_uri=entity.uri,
        source_hash=entity.source_hash,
        version=entity.version,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _chunk_metadata_from_row(chunk: ChunkModel) -> ChunkMetadata:
    raw = chunk.chunk_metadata or {}
    return ChunkMetadata.model_validate(raw)


def _chunk_to_schema(entity: ChunkModel) -> RagChunk:
    metadata = _chunk_metadata_from_row(entity)
    return RagChunk(
        id=entity.id,
        document_id=entity.document_id,
        organization_id=entity.organization_id,
        user_id=entity.user_id,
        title=metadata.title,
        section_title=metadata.section_title,
        page_number=metadata.page_number,
        chunk_ordinal=entity.ordinal,
        content=entity.content,
        token_count=entity.token_count,
        text_hash=entity.text_hash,
        embedding_ref=entity.embedding_ref,
        metadata=metadata,
        created_at=entity.created_at,
    )


def _citation_from_chunk(
    chunk: ChunkModel,
    metadata: ChunkMetadata,
    *,
    score: float | None = None,
) -> Citation:
    snippet = chunk.content[:240] + ("..." if len(chunk.content) > 240 else "")
    return Citation(
        document_id=chunk.document_id,
        chunk_id=chunk.id,
        title=metadata.title,
        source_type=metadata.source_type,
        section_title=metadata.section_title,
        page_number=metadata.page_number,
        chunk_ordinal=chunk.ordinal,
        score=score,
        snippet=snippet,
    )
