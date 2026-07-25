"""Repository for paper-signal orchestration decisions (AT-038)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import PaperSignalOrchestrationDecision as DecisionModel
from app.schemas.common import PaperSignalOrchestrationStatus


class PaperSignalOrchestrationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: DecisionModel) -> DecisionModel:
        self._session.add(row)
        self._session.flush()
        return row

    def get_for_org(
        self, decision_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> DecisionModel | None:
        return self._session.scalars(
            select(DecisionModel).where(
                DecisionModel.id == decision_id,
                DecisionModel.organization_id == organization_id,
            )
        ).first()

    def get_by_signal(
        self, *, organization_id: uuid.UUID, tradingview_signal_id: uuid.UUID
    ) -> DecisionModel | None:
        return self._session.scalars(
            select(DecisionModel).where(
                DecisionModel.organization_id == organization_id,
                DecisionModel.tradingview_signal_id == tradingview_signal_id,
            )
        ).first()

    def get_by_idempotency(
        self, *, organization_id: uuid.UUID, idempotency_key: str
    ) -> DecisionModel | None:
        return self._session.scalars(
            select(DecisionModel).where(
                DecisionModel.organization_id == organization_id,
                DecisionModel.idempotency_key == idempotency_key,
            )
        ).first()

    def list_for_org(
        self,
        *,
        organization_id: uuid.UUID,
        status: PaperSignalOrchestrationStatus | None = None,
        symbol: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DecisionModel], int]:
        filters = [DecisionModel.organization_id == organization_id]
        if status is not None:
            filters.append(DecisionModel.status == status.value)
        if symbol is not None:
            filters.append(DecisionModel.symbol == symbol.upper())
        total = self._session.scalar(
            select(func.count()).select_from(DecisionModel).where(*filters)
        )
        rows = list(
            self._session.scalars(
                select(DecisionModel)
                .where(*filters)
                .order_by(DecisionModel.updated_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return rows, int(total or 0)
