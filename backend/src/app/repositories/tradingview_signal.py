"""TradingView signal repository (AT-037)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import TradingViewSignal as SignalModel


class TradingViewSignalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: SignalModel) -> SignalModel:
        self._session.add(row)
        self._session.flush()
        return row

    def get_for_org(
        self,
        signal_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> SignalModel | None:
        stmt = select(SignalModel).where(
            SignalModel.id == signal_id,
            SignalModel.organization_id == organization_id,
        )
        return self._session.scalars(stmt).first()

    def get_by_idempotency(
        self,
        *,
        organization_id: uuid.UUID,
        idempotency_key: str,
    ) -> SignalModel | None:
        stmt = select(SignalModel).where(
            SignalModel.organization_id == organization_id,
            SignalModel.idempotency_key == idempotency_key,
        )
        return self._session.scalars(stmt).first()

    def get_by_alert_id(
        self,
        *,
        organization_id: uuid.UUID,
        external_alert_id: str,
    ) -> SignalModel | None:
        stmt = select(SignalModel).where(
            SignalModel.organization_id == organization_id,
            SignalModel.external_alert_id == external_alert_id,
        )
        return self._session.scalars(stmt).first()

    def list_for_org(
        self,
        *,
        organization_id: uuid.UUID,
        status: str | None = None,
        symbol: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SignalModel], int]:
        filters = [SignalModel.organization_id == organization_id]
        if status is not None:
            filters.append(SignalModel.status == status)
        if symbol is not None:
            filters.append(SignalModel.symbol == symbol)
        count_stmt = select(func.count()).select_from(SignalModel).where(*filters)
        total = int(self._session.scalar(count_stmt) or 0)
        stmt = (
            select(SignalModel)
            .where(*filters)
            .order_by(SignalModel.received_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(stmt).all()), total
