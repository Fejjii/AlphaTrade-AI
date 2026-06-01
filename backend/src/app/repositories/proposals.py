"""Trade proposal persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db.models import TradeProposal
from app.repositories.base import SQLAlchemyRepository


class ProposalRepository(SQLAlchemyRepository[TradeProposal]):
    model = TradeProposal

    def list_proposals(
        self,
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TradeProposal], int]:
        filters = []
        if organization_id is not None:
            filters.append(TradeProposal.organization_id == organization_id)
        if user_id is not None:
            filters.append(TradeProposal.user_id == user_id)

        count_stmt = select(func.count()).select_from(TradeProposal)
        list_stmt = select(TradeProposal).order_by(TradeProposal.created_at.desc())
        if filters:
            count_stmt = count_stmt.where(*filters)
            list_stmt = list_stmt.where(*filters)
        total = int(self._session.scalar(count_stmt) or 0)
        return list(self._session.scalars(list_stmt.limit(limit).offset(offset)).all()), total

    def get_scoped(
        self,
        proposal_id: uuid.UUID,
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> TradeProposal | None:
        stmt = select(TradeProposal).where(TradeProposal.id == proposal_id)
        if organization_id is not None:
            stmt = stmt.where(TradeProposal.organization_id == organization_id)
        if user_id is not None:
            stmt = stmt.where(TradeProposal.user_id == user_id)
        return self._session.scalar(stmt)
