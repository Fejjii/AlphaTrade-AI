"""Canonical journal trade persistence (AT-030)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import (
    JournalTrade,
    JournalTradeEvidence,
    JournalTradeObservation,
    JournalTradeRuleCheck,
)
from app.repositories.base import SQLAlchemyRepository
from app.schemas.common import JournalTradeSource, JournalTradeStatus


class JournalTradeRepository(SQLAlchemyRepository[JournalTrade]):
    model = JournalTrade

    def list_trades(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        source: JournalTradeSource | None = None,
        status: JournalTradeStatus | None = None,
        symbol: str | None = None,
        user_strategy_id: uuid.UUID | None = None,
        setup_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[JournalTrade], int]:
        filters = [JournalTrade.organization_id == organization_id]
        if user_id is not None:
            filters.append(JournalTrade.user_id == user_id)
        if source is not None:
            filters.append(JournalTrade.source == source)
        if status is not None:
            filters.append(JournalTrade.status == status)
        if symbol is not None:
            filters.append(JournalTrade.symbol == symbol)
        if user_strategy_id is not None:
            filters.append(JournalTrade.user_strategy_id == user_strategy_id)
        if setup_id is not None:
            filters.append(JournalTrade.setup_id == setup_id)

        count_stmt = select(func.count()).select_from(JournalTrade).where(*filters)
        list_stmt = (
            select(JournalTrade)
            .where(*filters)
            .order_by(JournalTrade.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        total = int(self._session.scalar(count_stmt) or 0)
        return list(self._session.scalars(list_stmt).all()), total

    def get_scoped(
        self,
        trade_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> JournalTrade | None:
        stmt = select(JournalTrade).where(
            JournalTrade.id == trade_id,
            JournalTrade.organization_id == organization_id,
        )
        return self._session.scalar(stmt)

    def find_by_link(
        self,
        *,
        organization_id: uuid.UUID,
        linked_position_id: uuid.UUID | None = None,
        linked_paper_trade_id: uuid.UUID | None = None,
    ) -> JournalTrade | None:
        stmt = select(JournalTrade).where(JournalTrade.organization_id == organization_id)
        if linked_position_id is not None:
            stmt = stmt.where(JournalTrade.linked_position_id == linked_position_id)
        if linked_paper_trade_id is not None:
            stmt = stmt.where(JournalTrade.linked_paper_trade_id == linked_paper_trade_id)
        return self._session.scalar(stmt.limit(1))


class JournalTradeEvidenceRepository(SQLAlchemyRepository[JournalTradeEvidence]):
    model = JournalTradeEvidence

    def list_for_trade(self, journal_trade_id: uuid.UUID) -> list[JournalTradeEvidence]:
        stmt = (
            select(JournalTradeEvidence)
            .where(JournalTradeEvidence.journal_trade_id == journal_trade_id)
            .order_by(JournalTradeEvidence.created_at.asc())
        )
        return list(self._session.scalars(stmt).all())


class JournalTradeRuleCheckRepository(SQLAlchemyRepository[JournalTradeRuleCheck]):
    model = JournalTradeRuleCheck

    def list_for_trade(self, journal_trade_id: uuid.UUID) -> list[JournalTradeRuleCheck]:
        stmt = (
            select(JournalTradeRuleCheck)
            .where(JournalTradeRuleCheck.journal_trade_id == journal_trade_id)
            .order_by(JournalTradeRuleCheck.created_at.asc())
        )
        return list(self._session.scalars(stmt).all())


class JournalTradeObservationRepository(SQLAlchemyRepository[JournalTradeObservation]):
    model = JournalTradeObservation

    def list_for_trade(self, journal_trade_id: uuid.UUID) -> list[JournalTradeObservation]:
        stmt = (
            select(JournalTradeObservation)
            .where(JournalTradeObservation.journal_trade_id == journal_trade_id)
            .order_by(JournalTradeObservation.created_at.asc())
        )
        return list(self._session.scalars(stmt).all())
