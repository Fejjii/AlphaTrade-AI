"""Knowledge and strategy retrieval over existing stores.

Lexical search reads `documents` and `chunks`. Optional vector hits are
accepted only when the chunk row reloads inside the caller's tenant.
"""

from __future__ import annotations

import uuid
from typing import Literal, Protocol

import structlog
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import Chunk, Document
from app.interactive_agent.contracts import KnowledgeHit, ProvenanceSource, StrategyHit
from app.interactive_agent.parsing import query_tokens
from app.schemas.common import DocumentSourceType
from app.schemas.strategy_library import UserStrategy
from app.services.strategy_library_service import StrategyLibraryService

logger = structlog.get_logger(__name__)

_SCAN_LIMIT = 200
_USER_SOURCE_TYPES = frozenset(
    {
        DocumentSourceType.TRADE_JOURNAL.value,
        DocumentSourceType.REVIEW_NOTE.value,
        DocumentSourceType.MISTAKES_DATABASE.value,
        DocumentSourceType.GENERAL_NOTE.value,
        DocumentSourceType.STRATEGY_TEMPLATE.value,
    }
)


class VectorKnowledgeRetriever(Protocol):
    """Optional adapter. Implementations must not be treated as tenant-safe."""

    def search(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        query: str,
        limit: int,
    ) -> list[KnowledgeHit]: ...


def provenance_for_source(source_type: str) -> ProvenanceSource:
    """Map a stored document source to content provenance."""
    if source_type in _USER_SOURCE_TYPES:
        return ProvenanceSource.USER_SUPPLIED
    return ProvenanceSource.SYSTEM_GENERATED


def _snippet(content: str) -> str:
    compact = " ".join(content.split())
    return compact[:240]


def _hit_from_row(
    chunk: Chunk,
    document: Document,
    *,
    mode: str,
    match_count: int,
) -> KnowledgeHit | None:
    if document.organization_id is None or chunk.organization_id is None:
        return None
    title = document.title.strip() or "Untitled"
    snippet = _snippet(chunk.content)
    source = document.source_type
    source_name = source.value if isinstance(source, DocumentSourceType) else str(source)
    retrieval_mode: Literal["lexical_store", "vector"] = (
        "vector" if mode == "vector" else "lexical_store"
    )
    return KnowledgeHit(
        chunk_id=chunk.id,
        document_id=document.id,
        organization_id=document.organization_id,
        user_id=document.user_id,
        title=title[:255],
        source_type=source_name,
        snippet=snippet,
        match_count=match_count,
        provenance=provenance_for_source(source_name),
        retrieval_mode=retrieval_mode,
    )


def _load_scoped_chunk(
    session: Session,
    chunk_id: uuid.UUID,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[Chunk, Document] | None:
    chunk = session.get(Chunk, chunk_id)
    if chunk is None or chunk.organization_id != organization_id:
        return None
    if chunk.user_id is not None and chunk.user_id != user_id:
        return None
    document = session.get(Document, chunk.document_id)
    if document is None or document.organization_id != organization_id:
        return None
    if document.user_id is not None and document.user_id != user_id:
        return None
    return chunk, document


def _lexical_hits(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    tokens: set[str],
    limit: int,
) -> list[KnowledgeHit]:
    stmt = (
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.organization_id == organization_id)
        .where(Chunk.organization_id == organization_id)
        .where(or_(Document.user_id.is_(None), Document.user_id == user_id))
        .where(or_(Chunk.user_id.is_(None), Chunk.user_id == user_id))
        .limit(_SCAN_LIMIT)
    )
    ranked: list[tuple[int, KnowledgeHit]] = []
    for chunk, document in session.execute(stmt).all():
        overlap = query_tokens(f"{document.title} {chunk.content}") & tokens
        if not overlap:
            continue
        hit = _hit_from_row(chunk, document, mode="lexical_store", match_count=len(overlap))
        if hit is not None:
            ranked.append((len(overlap), hit))
    ranked.sort(key=lambda item: (-item[0], item[1].title))
    return [hit for _, hit in ranked[:limit]]


def retrieve_knowledge(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    limit: int = 5,
    vector_retriever: VectorKnowledgeRetriever | None = None,
) -> tuple[list[KnowledgeHit], list[str]]:
    """Return tenant-scoped knowledge hits and honest retrieval limitations."""
    limitations = [
        "Knowledge retrieval reads the existing document and chunk store. "
        "Qdrant is not queried unless a vector retriever is injected."
    ]
    tokens = query_tokens(query)
    if vector_retriever is not None:
        verified, notes = _verified_vector_hits(
            session,
            retriever=vector_retriever,
            organization_id=organization_id,
            user_id=user_id,
            query=query,
            tokens=tokens,
            limit=limit,
        )
        limitations.extend(notes)
        if verified:
            return verified, limitations
    if not tokens:
        return [], limitations
    limitations.append("Lexical retrieval scanned at most 200 chunks.")
    return (
        _lexical_hits(
            session,
            organization_id=organization_id,
            user_id=user_id,
            tokens=tokens,
            limit=limit,
        ),
        limitations,
    )


def _verified_vector_hits(
    session: Session,
    *,
    retriever: VectorKnowledgeRetriever,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    tokens: set[str],
    limit: int,
) -> tuple[list[KnowledgeHit], list[str]]:
    try:
        raw = retriever.search(
            organization_id=organization_id,
            user_id=user_id,
            query=query,
            limit=limit,
        )
    except Exception:
        logger.warning("interactive_agent_vector_retrieval_failed")
        return [], ["Vector retrieval failed. Lexical chunk search was used."]
    verified: list[KnowledgeHit] = []
    dropped = False
    for hit in raw:
        loaded = _load_scoped_chunk(
            session,
            hit.chunk_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if loaded is None:
            dropped = True
            continue
        chunk, document = loaded
        overlap = len(query_tokens(chunk.content) & tokens)
        rebuilt = _hit_from_row(chunk, document, mode="vector", match_count=overlap)
        if rebuilt is None:
            dropped = True
            continue
        verified.append(rebuilt)
    notes = ["Vector hits were reloaded from the chunk store before use."]
    if dropped:
        notes.append("Vector hits outside the tenant knowledge store were dropped.")
    return verified[:limit], notes


def _strategy_summary(name: str, setup_type: str, status: str | None, entry: str | None) -> str:
    label = status or "unspecified"
    text = f"{name} ({setup_type}, {label})"
    if entry:
        text = f"{text}: {entry}"
    return text[:300]


def retrieve_strategies(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    list_all: bool,
    strategy_id: uuid.UUID | None,
    limit: int = 8,
) -> tuple[list[StrategyHit], list[str]]:
    """Read the caller's strategy library. This does not create or update rows."""
    limitations: list[str] = []
    library = StrategyLibraryService(session)
    hits: list[StrategyHit] = []
    seen: set[uuid.UUID] = set()
    if strategy_id is not None:
        try:
            bound = library.get(strategy_id, organization_id=organization_id, user_id=user_id)
        except NotFoundError:
            limitations.append("The requested strategy is not in this tenant.")
        else:
            hits.append(_to_strategy_hit(bound))
            seen.add(bound.id)
    rows, total = library.list_strategies(
        organization_id=organization_id,
        user_id=user_id,
        limit=50,
        offset=0,
    )
    if total > len(rows):
        limitations.append("Strategy retrieval scanned the 50 most recently updated strategies.")
    tokens = query_tokens(query)
    for row in rows:
        if row.id in seen:
            continue
        blob = " ".join(
            part for part in (row.name, row.setup_type.value, row.notes or "", row.name) if part
        )
        if row.latest_card is not None:
            blob = " ".join(
                [blob, *row.latest_card.entry_conditions, *row.latest_card.invalidation]
            )
        matched = list_all or bool(query_tokens(blob) & tokens)
        if not matched:
            continue
        hits.append(_to_strategy_hit(row))
        seen.add(row.id)
        if len(hits) >= limit:
            break
    return hits[:limit], limitations


def _to_strategy_hit(item: UserStrategy) -> StrategyHit:
    entry = None
    if item.latest_card is not None and item.latest_card.entry_conditions:
        entry = item.latest_card.entry_conditions[0][:160]
    status = item.validation_status.value if item.validation_status is not None else None
    return StrategyHit(
        strategy_id=item.id,
        name=item.name,
        setup_type=item.setup_type.value,
        version=item.current_version,
        validation_status=status,
        paper_eligible=item.paper_eligible,
        summary=_strategy_summary(item.name, item.setup_type.value, status, entry),
    )
