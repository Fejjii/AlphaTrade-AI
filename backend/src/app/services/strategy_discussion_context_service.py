"""Read-only strategy discussion context from existing authorities.

This is not a memory store. Facts come from the strategy library, lessons,
journal, learning attribution, and RAG. Conversation transcripts stay separate.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.learning_attribution.query import LearningQueryService
from app.persistence.attribution_postgres import PostgresAttributionStore
from app.schemas.common import DocumentSourceType, LessonCandidateStatus
from app.schemas.conversation import StrategyDiscussionContext
from app.schemas.rag import RagQuery
from app.services.audit_service import AuditService
from app.services.journal_trade_service import JournalTradeService
from app.services.lesson_candidate_service import LessonCandidateService
from app.services.rag_service import RagService
from app.services.strategy_library_service import StrategyLibraryService


class StrategyDiscussionContextService:
    def __init__(
        self,
        session: Session,
        *,
        rag_service: RagService | None = None,
    ) -> None:
        self._session = session
        self._strategies = StrategyLibraryService(session)
        self._lessons = LessonCandidateService(session)
        self._journal = JournalTradeService(session, AuditService(session))
        self._learning = LearningQueryService(PostgresAttributionStore(session))
        self._rag = rag_service

    def gather(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        strategy_id: uuid.UUID | None,
        query: str,
    ) -> StrategyDiscussionContext:
        limitations = [
            "Context is assembled from existing authorities. "
            "Conversation memory is not a source of truth.",
            "Learning stats do not auto-promote rules.",
            "No Watcher, Telegram, or live trading context is implied.",
        ]
        strategy_payload: dict[str, Any] | None = None
        versions: list[dict[str, Any]] = []
        if strategy_id is not None:
            try:
                strategy_payload = self._strategies.get(
                    strategy_id, organization_id=organization_id, user_id=user_id
                ).model_dump(mode="json")
                listed, _ = self._strategies.list_versions(
                    strategy_id, organization_id=organization_id, user_id=user_id, limit=10
                )
                versions = [item.model_dump(mode="json") for item in listed]
            except Exception:
                strategy_payload = None

        lessons_payload: list[dict[str, Any]] = []
        try:
            pending, _ = self._lessons.list_candidates(
                organization_id=organization_id,
                user_id=user_id,
                status=LessonCandidateStatus.PENDING_REVIEW,
                limit=10,
            )
            accepted, _ = self._lessons.list_candidates(
                organization_id=organization_id,
                user_id=user_id,
                status=LessonCandidateStatus.ACCEPTED,
                limit=10,
            )
            combined = [*pending, *accepted]
            if strategy_id is not None:
                combined = [item for item in combined if item.related_strategy_id == strategy_id]
            lessons_payload = [item.model_dump(mode="json") for item in combined[:10]]
        except Exception:
            lessons_payload = []

        trades_payload: list[dict[str, Any]] = []
        try:
            trades, _ = self._journal.list_trades(
                organization_id=organization_id,
                user_id=user_id,
                user_strategy_id=strategy_id,
                limit=5,
            )
            trades_payload = [item.model_dump(mode="json") for item in trades]
        except Exception:
            trades_payload = []

        stats: dict[str, Any] | None = None
        try:
            snapshot = self._learning.strategy_pattern_stats(organization_id=organization_id)
            stats = snapshot.model_dump(mode="json")
        except Exception:
            stats = None

        citations: list[dict[str, Any]] = []
        if self._rag is not None and query.strip():
            source_types = [
                DocumentSourceType.TRADE_JOURNAL,
                DocumentSourceType.REVIEW_NOTE,
                DocumentSourceType.MISTAKES_DATABASE,
                DocumentSourceType.TRADING_PLAYBOOK,
                DocumentSourceType.RISK_POLICY,
            ]
            if strategy_id is not None:
                source_types.append(DocumentSourceType.STRATEGY_TEMPLATE)
            try:
                result = self._rag.search(
                    RagQuery(
                        query=query[:500],
                        organization_id=organization_id,
                        user_id=user_id,
                        top_k=5,
                        source_types=source_types,
                    )
                )
                citations = [cite.model_dump(mode="json") for cite in result.citations]
            except Exception:
                citations = []

        return StrategyDiscussionContext(
            strategy=strategy_payload,
            versions=versions,
            lessons=lessons_payload,
            journal_trades=trades_payload,
            learning_stats=stats,
            rag_citations=citations,
            limitations=limitations,
        )
