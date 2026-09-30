"""Read-through adapters. Failures become limitations and never invented facts."""

from __future__ import annotations

import uuid
from typing import Protocol

import structlog
from pydantic import Field
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.interactive_agent.canonical_market import CanonicalMarketStateError
from app.interactive_agent.contracts import (
    AgentCapability,
    ArtifactKind,
    ConnectionRef,
    MarketQuoteView,
    ProvenanceSource,
)
from app.interactive_agent.parsing import extract_symbol, query_tokens
from app.repositories.market_watcher import MarketWatcherObservationRepository
from app.schemas.common import StrictModel, TradeResult
from app.services.audit_service import AuditService
from app.services.coaching.service import CoachingService
from app.services.journal_service import JournalService
from app.services.paper_portfolio_service import PaperPortfolioService
from app.services.performance_service import PerformanceService
from app.services.strategy_library_service import StrategyLibraryService

logger = structlog.get_logger(__name__)


class MarketQuoteReader(Protocol):
    """Supplies a quote that already carries source and freshness flags."""

    def quote(self, symbol: str) -> MarketQuoteView: ...


class ReadBundle(StrictModel):
    market_quote: MarketQuoteView | None = None
    market_availability: str | None = None
    market_reason: str | None = None
    portfolio_summary: str | None = None
    statistics_summary: str | None = None
    coaching_note: str | None = None
    connections: list[ConnectionRef] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    invalidation: list[str] = Field(default_factory=list)
    stop_loss: list[str] = Field(default_factory=list)


def gather_reads(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    message: str,
    capability: AgentCapability,
    strategy_id: uuid.UUID | None,
    market_reader: MarketQuoteReader | None,
    symbol: str | None = None,
) -> ReadBundle:
    """Read existing authorities for this turn. No snapshots or journal writes."""
    bundle = ReadBundle()
    if capability is AgentCapability.MARKET_AND_PORTFOLIO:
        _read_quote(bundle, message, market_reader, symbol_hint=symbol)
        _read_portfolio(session, bundle, organization_id=organization_id, user_id=user_id)
    if capability is AgentCapability.STATISTICS_AND_PERFORMANCE:
        _read_statistics(session, bundle, organization_id=organization_id, user_id=user_id)
    if capability is AgentCapability.POST_TRADE_REFLECTION:
        _read_coaching(session, bundle, organization_id=organization_id, user_id=user_id)
    if capability is AgentCapability.MARKET_AND_PORTFOLIO or "watcher" in message.lower():
        _read_watcher(session, bundle, organization_id=organization_id, message=message)
    _read_journal(
        session,
        bundle,
        organization_id=organization_id,
        user_id=user_id,
        message=message,
    )
    if strategy_id is not None and capability is AgentCapability.PRE_TRADE_REASONING:
        _read_strategy_levels(
            session,
            bundle,
            organization_id=organization_id,
            user_id=user_id,
            strategy_id=strategy_id,
        )
    return bundle


def _read_quote(
    bundle: ReadBundle,
    message: str,
    reader: MarketQuoteReader | None,
    *,
    symbol_hint: str | None = None,
) -> None:
    symbol = extract_symbol(message) or _symbol_hint(symbol_hint)
    if symbol is None:
        bundle.limitations.append("No symbol was named, so no market quote was fetched.")
        return
    if reader is None:
        bundle.limitations.append("No market-data reader is configured, so no quote was fetched.")
        return
    try:
        bundle.market_quote = reader.quote(symbol)
    except CanonicalMarketStateError as exc:
        bundle.market_availability = exc.availability
        bundle.market_reason = exc.reason
        bundle.limitations.append(
            f"Canonical perpetual evidence for {symbol} is {exc.availability}. "
            f"{exc.reason} No price was invented."
        )
        return
    except Exception:
        logger.warning("interactive_agent_quote_unavailable")
        bundle.limitations.append("The market-data reader failed. No quote was invented.")
        return
    if bundle.market_quote is not None and bundle.market_quote.is_stale:
        bundle.market_availability = "stale"
        bundle.limitations.append(
            f"Canonical perpetual evidence for {symbol} is stale. "
            "The price is not a current market price."
        )


def _symbol_hint(value: str | None) -> str | None:
    if value is None:
        return None
    token = value.strip().upper()
    if len(token) < 2 or len(token) > 30 or not token.isalnum():
        return None
    return token


def _read_portfolio(
    session: Session,
    bundle: ReadBundle,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    try:
        portfolio = PaperPortfolioService(session).build_portfolio(
            organization_id=organization_id,
            user_id=user_id,
        )
    except Exception:
        logger.warning("interactive_agent_portfolio_unavailable")
        bundle.limitations.append("Paper portfolio was not available for this turn.")
        return
    account = portfolio.account
    bundle.portfolio_summary = (
        f"Paper portfolio equity {account.current_equity} with "
        f"{account.open_trade_count} open and {account.closed_trade_count} closed trades. "
        "real_trading_enabled is false."
    )[:500]


def _read_statistics(
    session: Session,
    bundle: ReadBundle,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    try:
        report = PerformanceService(session).build_report(
            organization_id=organization_id,
            user_id=user_id,
        )
    except Exception:
        logger.warning("interactive_agent_statistics_unavailable")
        bundle.limitations.append("Performance report was not available for this turn.")
        return
    metrics = report.account
    bundle.statistics_summary = (
        f"Stored paper positions: {metrics.trade_count} closed trades, "
        f"net PnL {metrics.net_pnl}, win rate {metrics.win_rate}. "
        "Figures come from the performance calculator."
    )[:500]


def _read_coaching(
    session: Session,
    bundle: ReadBundle,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    try:
        summary = CoachingService(session).summary(
            organization_id=organization_id,
            user_id=user_id,
            start_date=None,
            end_date=None,
            min_sample=5,
        )
    except Exception:
        logger.warning("interactive_agent_coaching_unavailable")
        bundle.limitations.append("Coaching summary was not available for this turn.")
        return
    bundle.coaching_note = (
        f"Coaching summary lists {summary.total_open} open prompts and "
        f"{summary.pending_coaching_lessons} pending coaching lessons. "
        "None were accepted by this turn."
    )


def _read_watcher(
    session: Session,
    bundle: ReadBundle,
    *,
    organization_id: uuid.UUID,
    message: str,
) -> None:
    try:
        rows, _total = MarketWatcherObservationRepository(session).list_for_org(
            organization_id,
            symbol=extract_symbol(message),
            limit=3,
        )
    except Exception:
        logger.warning("interactive_agent_watcher_unavailable")
        bundle.limitations.append("Watcher observations were not available for this turn.")
        return
    for row in rows:
        status = row.status.value if hasattr(row.status, "value") else str(row.status)
        bundle.connections.append(
            ConnectionRef(
                artifact_kind=ArtifactKind.OBSERVATION,
                record_id=str(row.id),
                title=f"{row.symbol} {row.timeframe} {status}"[:200],
                relation="watcher observation",
                provenance=ProvenanceSource.WATCHER_OBSERVED,
            )
        )


def _read_journal(
    session: Session,
    bundle: ReadBundle,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    message: str,
) -> None:
    try:
        entries, _total = JournalService(session, AuditService(session)).list_entries(
            organization_id=organization_id,
            user_id=user_id,
            limit=20,
        )
    except Exception:
        logger.warning("interactive_agent_journal_read_unavailable")
        bundle.limitations.append("Journal entries were not available for this turn.")
        return
    tokens = query_tokens(message)
    symbol = extract_symbol(message)
    for entry in entries:
        blob = f"{entry.symbol} {entry.entry_rationale}"
        overlap = bool(query_tokens(blob) & tokens) or (
            symbol is not None and entry.symbol.upper() == symbol
        )
        if not overlap:
            continue
        provenance = (
            ProvenanceSource.TRADE_OUTCOME
            if entry.result in {TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN}
            else ProvenanceSource.USER_SUPPLIED
        )
        bundle.connections.append(
            ConnectionRef(
                artifact_kind=ArtifactKind.JOURNAL_ENTRY,
                record_id=str(entry.id),
                title=f"{entry.symbol} {entry.direction.value} journal"[:200],
                relation="matching journal entry",
                provenance=provenance,
            )
        )


def _read_strategy_levels(
    session: Session,
    bundle: ReadBundle,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    strategy_id: uuid.UUID,
) -> None:
    try:
        strategy = StrategyLibraryService(session).get(
            strategy_id,
            organization_id=organization_id,
            user_id=user_id,
        )
    except NotFoundError:
        bundle.limitations.append("No strategy levels were loaded for this tenant.")
        return
    card = strategy.latest_card
    if card is None:
        bundle.limitations.append("The bound strategy has no card, so no levels were copied.")
        return
    bundle.invalidation = list(card.invalidation)
    bundle.stop_loss = list(card.stop_loss)
