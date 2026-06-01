"""RAG document and chunk schemas.

Vectors live in Qdrant; document/chunk metadata lives in PostgreSQL. Metadata
filters (user, org, source type, strategy/symbol/timeframe/risk tags) drive
scoped retrieval, and responses always carry citations (master prompt §14).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import DocumentSourceType, ORMModel, StrictModel


class ChunkMetadata(StrictModel):
    """Filterable metadata attached to a chunk for scoped retrieval."""

    title: str | None = None
    section_title: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    source_type: DocumentSourceType
    strategy_tag: str | None = None
    symbol_tag: str | None = None
    timeframe_tag: str | None = None
    risk_tag: str | None = None


class RagDocument(ORMModel):
    """A source document in the knowledge base."""

    id: UUID
    organization_id: UUID | None = None
    user_id: UUID | None = None
    source_type: DocumentSourceType
    title: str
    source_uri: str | None = None
    source_hash: str | None = None
    version: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime


class RagChunk(ORMModel):
    """A retrievable chunk of a document."""

    id: UUID
    document_id: UUID
    organization_id: UUID | None = None
    user_id: UUID | None = None
    title: str | None = None
    section_title: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    chunk_ordinal: int = Field(ge=0)
    content: str
    token_count: int | None = Field(default=None, ge=0)
    text_hash: str | None = None
    embedding_ref: str | None = Field(default=None, description="Qdrant point id, if embedded.")
    metadata: ChunkMetadata
    created_at: datetime


class Citation(ORMModel):
    """A citation returned alongside RAG-grounded answers."""

    document_id: UUID
    chunk_id: UUID
    title: str | None = None
    source_type: DocumentSourceType
    section_title: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    chunk_ordinal: int | None = Field(default=None, ge=0)
    score: float | None = Field(default=None, ge=0, le=1)
    snippet: str | None = None


class RagQuery(StrictModel):
    """A scoped retrieval request."""

    query: str = Field(min_length=1, max_length=2000)
    organization_id: UUID | None = None
    user_id: UUID | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    source_types: list[DocumentSourceType] = Field(default_factory=list)
    strategy_tag: str | None = None
    symbol_tag: str | None = None
    timeframe_tag: str | None = None
    risk_tag: str | None = None


class DocumentCreateRequest(StrictModel):
    """Register document metadata without ingesting body text."""

    organization_id: UUID | None = None
    user_id: UUID | None = None
    source_type: DocumentSourceType
    title: str = Field(min_length=1, max_length=255)
    source_uri: str | None = Field(default=None, max_length=1024)
    version: int = Field(default=1, ge=1)


class IngestDocumentRequest(StrictModel):
    """Ingest plain text into the knowledge base."""

    organization_id: UUID | None = None
    user_id: UUID | None = None
    source_type: DocumentSourceType
    title: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1)
    source_uri: str | None = Field(default=None, max_length=1024)
    version: int = Field(default=1, ge=1)
    strategy_tag: str | None = None
    symbol_tag: str | None = None
    timeframe_tag: str | None = None
    risk_tag: str | None = None


class IngestDocumentResponse(ORMModel):
    """Summary returned after document ingestion."""

    document_id: UUID
    source_hash: str
    chunk_count: int = Field(ge=0)
    duplicate: bool = False
    version: int = Field(ge=1)


class RetrievedChunk(ORMModel):
    """A ranked chunk returned from retrieval."""

    chunk_id: UUID
    document_id: UUID
    title: str | None = None
    section_title: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    chunk_ordinal: int = Field(ge=0)
    source_type: DocumentSourceType
    content: str
    score: float = Field(ge=0, le=1)


class RagSearchResponse(StrictModel):
    """Retrieval results with citations."""

    query: str
    chunks: list[RetrievedChunk]
    citations: list[Citation]


class PaginatedRagDocuments(StrictModel):
    items: list[RagDocument]
    total: int
    limit: int
    offset: int


class PaginatedRagChunks(StrictModel):
    items: list[RagChunk]
    total: int
    limit: int
    offset: int
