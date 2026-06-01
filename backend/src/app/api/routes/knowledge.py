"""Knowledge base / RAG API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.core.auth import TenantDep
from app.core.dependencies import RagServiceDep
from app.schemas.common import DocumentSourceType
from app.schemas.rag import (
    DocumentCreateRequest,
    IngestDocumentRequest,
    IngestDocumentResponse,
    PaginatedRagChunks,
    PaginatedRagDocuments,
    RagDocument,
    RagQuery,
    RagSearchResponse,
)
from app.security.quota_enforcement import require_quota
from app.security.rate_limit import tenant_rate_limit_dependency
from app.security.rbac import TraderDep

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_KNOWLEDGE_INGEST_RATE_LIMIT = Depends(
    tenant_rate_limit_dependency(
        "knowledge:ingest",
        limit=20,
        window_seconds=3600,
        ip_limit=40,
        user_limit=20,
    )
)
_RAG_INGEST_QUOTA = require_quota("rag_ingest")


@router.post(
    "/documents",
    response_model=RagDocument,
    summary="Register knowledge document metadata",
)
async def create_document(
    body: DocumentCreateRequest,
    tenant: TraderDep,
    rag_service: RagServiceDep,
) -> RagDocument:
    payload = body.model_copy(
        update={"organization_id": tenant.organization_id, "user_id": tenant.user_id}
    )
    document = rag_service.create_document(payload)
    return document


@router.post(
    "/ingest",
    response_model=IngestDocumentResponse,
    summary="Ingest plain-text document into the knowledge base",
    dependencies=[_KNOWLEDGE_INGEST_RATE_LIMIT, _RAG_INGEST_QUOTA],
)
async def ingest_document(
    body: IngestDocumentRequest,
    tenant: TraderDep,
    rag_service: RagServiceDep,
) -> IngestDocumentResponse:
    payload = body.model_copy(
        update={"organization_id": tenant.organization_id, "user_id": tenant.user_id}
    )
    return rag_service.ingest(payload)


@router.get(
    "/documents",
    response_model=PaginatedRagDocuments,
    summary="List knowledge documents",
)
async def list_documents(
    tenant: TenantDep,
    rag_service: RagServiceDep,
    source_type: DocumentSourceType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedRagDocuments:
    items, total = rag_service.list_documents(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        source_type=source_type,
        limit=limit,
        offset=offset,
    )
    return PaginatedRagDocuments(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/chunks",
    response_model=PaginatedRagChunks,
    summary="List document chunks",
)
async def list_chunks(
    tenant: TenantDep,
    rag_service: RagServiceDep,
    document_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedRagChunks:
    items, total = rag_service.list_chunks(
        document_id=document_id,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        limit=limit,
        offset=offset,
    )
    return PaginatedRagChunks(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/search",
    response_model=RagSearchResponse,
    summary="Search the knowledge base",
)
async def search_knowledge(
    body: RagQuery,
    tenant: TenantDep,
    rag_service: RagServiceDep,
) -> RagSearchResponse:
    payload = body.model_copy(
        update={"organization_id": tenant.organization_id, "user_id": tenant.user_id}
    )
    return rag_service.search(payload)
