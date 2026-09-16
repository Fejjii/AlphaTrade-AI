"""Optional journal → RAG sync boundary (Slice 20).

Converts trade journal entries into searchable knowledge chunks. Sensitive patterns
(API keys, secrets) are stripped before ingestion.
"""

from __future__ import annotations

import re
import uuid

import structlog

from app.core.config import Settings
from app.db.models import JournalTrade, JournalTradeObservation, TradeJournal
from app.schemas.common import DocumentSourceType, JournalObservationCategory
from app.schemas.journal import JournalEntry
from app.schemas.rag import IngestDocumentRequest
from app.services.rag_service import RagService

logger = structlog.get_logger(__name__)

_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+[a-z0-9\-_.~+/]+=*"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
)


def sanitize_journal_text(text: str) -> str:
    """Remove likely secret material from journal text before RAG ingestion."""
    cleaned = text
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned.strip()


def build_journal_document_text(entry: JournalEntry | TradeJournal) -> str:
    """Render a journal entry as plain text for chunking."""
    timeframe = entry.timeframe.value if hasattr(entry.timeframe, "value") else str(entry.timeframe)
    direction = entry.direction.value if hasattr(entry.direction, "value") else str(entry.direction)
    strategy = None
    if entry.strategy_id:
        strategy = (
            entry.strategy_id.value
            if hasattr(entry.strategy_id, "value")
            else str(entry.strategy_id)
        )
    result = None
    if entry.result:
        result = entry.result.value if hasattr(entry.result, "value") else str(entry.result)

    lines = [
        "[PENDING_OBSERVATION — not a permanent trading rule until accepted in Lessons]",
        f"Symbol: {entry.symbol}",
        f"Timeframe: {timeframe}",
        f"Direction: {direction}",
    ]
    if strategy:
        lines.append(f"Setup type: {strategy}")
    if result:
        lines.append(f"Result: {result}")
    lines.append(f"Entry rationale: {entry.entry_rationale}")
    if entry.exit_rationale:
        lines.append(f"Exit rationale: {entry.exit_rationale}")
    if entry.emotions:
        lines.append(f"Emotion tags: {', '.join(entry.emotions)}")
    if entry.mistakes:
        lines.append(f"Mistake tags: {', '.join(entry.mistakes)}")
    if entry.improvement_rule:
        lines.append(f"Draft improvement (pending review): {entry.improvement_rule}")
    if entry.lessons:
        lines.append(f"Draft lessons (pending review): {entry.lessons}")
    if entry.tags:
        lines.append(f"Tags: {', '.join(entry.tags)}")
    return sanitize_journal_text("\n".join(lines))


class JournalRagSyncService:
    """Sync journal entries into the RAG knowledge base when enabled."""

    def __init__(self, rag_service: RagService, settings: Settings) -> None:
        self._rag = rag_service
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return self._settings.journal_rag_sync_enabled

    def sync_entry(self, entry: JournalEntry) -> uuid.UUID | None:
        """Ingest or update RAG content for a journal entry. Returns document id."""
        if not self.enabled:
            return None

        text = build_journal_document_text(entry)
        if not text:
            return None

        title = f"Journal: {entry.symbol} ({entry.timeframe})"
        request = IngestDocumentRequest(
            organization_id=entry.organization_id,
            user_id=entry.user_id,
            source_type=DocumentSourceType.TRADE_JOURNAL,
            title=title,
            text=text,
            source_uri=f"journal://{entry.id}",
            strategy_tag=entry.strategy_id.value if entry.strategy_id else None,
            symbol_tag=str(entry.symbol),
            timeframe_tag=entry.timeframe.value,
            risk_tag=entry.result.value if entry.result else None,
        )
        result = self._rag.upsert_linked_document(request)
        logger.info(
            "journal_rag_sync",
            journal_entry_id=str(entry.id),
            document_id=str(result.document_id),
            duplicate=result.duplicate,
            compatibility_fallback=True,
        )
        return result.document_id

    def sync_journal_trade(
        self,
        trade: JournalTrade,
        *,
        observations: list[JournalTradeObservation] | None = None,
    ) -> list[uuid.UUID]:
        """Ingest JournalTrade as the canonical RAG source.

        When the trade is linked to a legacy journal entry, also upsert
        ``journal://{legacy_id}`` so existing lineage remains resolvable.
        """
        if not self.enabled:
            return []
        text = build_journal_trade_document_text(trade, observations=observations or [])
        if not text:
            return []
        ids: list[uuid.UUID] = []
        title = f"Journal: {trade.symbol} ({trade.timeframe})"
        canonical = self._rag.upsert_linked_document(
            IngestDocumentRequest(
                organization_id=trade.organization_id,
                user_id=trade.user_id,
                source_type=DocumentSourceType.TRADE_JOURNAL,
                title=title,
                text=text,
                source_uri=f"journal-trade://{trade.id}",
                strategy_tag=trade.strategy_label,
                symbol_tag=str(trade.symbol),
                timeframe_tag=trade.timeframe,
                risk_tag=trade.result.value if trade.result else None,
            )
        )
        ids.append(canonical.document_id)
        logger.info(
            "journal_rag_sync",
            journal_trade_id=str(trade.id),
            document_id=str(canonical.document_id),
            duplicate=canonical.duplicate,
            compatibility_fallback=False,
        )
        if trade.linked_journal_entry_id is not None:
            legacy = self._rag.upsert_linked_document(
                IngestDocumentRequest(
                    organization_id=trade.organization_id,
                    user_id=trade.user_id,
                    source_type=DocumentSourceType.TRADE_JOURNAL,
                    title=title,
                    text=text,
                    source_uri=f"journal://{trade.linked_journal_entry_id}",
                    strategy_tag=trade.strategy_label,
                    symbol_tag=str(trade.symbol),
                    timeframe_tag=trade.timeframe,
                    risk_tag=trade.result.value if trade.result else None,
                )
            )
            ids.append(legacy.document_id)
        return ids


def build_journal_trade_document_text(
    trade: JournalTrade,
    *,
    observations: list[JournalTradeObservation],
) -> str:
    """Render a canonical journal trade as plain text for chunking."""
    direction = trade.direction.value if hasattr(trade.direction, "value") else str(trade.direction)
    result = trade.result.value if hasattr(trade.result, "value") else str(trade.result)
    emotions = [
        obs.observation
        for obs in observations
        if obs.category is JournalObservationCategory.EMOTIONAL
    ]
    mistakes = [
        obs.observation
        for obs in observations
        if obs.category is JournalObservationCategory.MISTAKE
    ]
    lessons = [
        obs.observation for obs in observations if obs.category is JournalObservationCategory.LESSON
    ]
    lines = [
        "[PENDING_OBSERVATION — not a permanent trading rule until accepted in Lessons]",
        f"Symbol: {trade.symbol}",
        f"Timeframe: {trade.timeframe}",
        f"Direction: {direction}",
    ]
    if trade.strategy_label:
        lines.append(f"Setup type: {trade.strategy_label}")
    if result:
        lines.append(f"Result: {result}")
    if trade.thesis:
        lines.append(f"Entry rationale: {trade.thesis}")
    if trade.exit_reason:
        lines.append(f"Exit rationale: {trade.exit_reason}")
    if emotions:
        lines.append(f"Emotion tags: {', '.join(emotions)}")
    if mistakes:
        lines.append(f"Mistake tags: {', '.join(mistakes)}")
    if lessons:
        lines.append(f"Draft lessons (pending review): {'; '.join(lessons)}")
    if trade.tags:
        lines.append(f"Tags: {', '.join(trade.tags)}")
    return sanitize_journal_text("\n".join(lines))
