"""Paper position management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import Position as PositionModel
from app.repositories.positions import PositionRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import ActorType, AuditEventType, PositionStatus, TradeDirection
from app.schemas.position import ClosePaperPositionRequest, Position, PositionUpdate
from app.schemas.proposal import TakeProfitLevel
from app.services.audit_service import AuditService


class PositionService:
    def __init__(self, session: Session, audit_service: AuditService) -> None:
        self._repo = PositionRepository(session)
        self._audit = audit_service

    def list_positions(
        self,
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        status: PositionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Position], int]:
        rows, total = self._repo.list_positions(
            organization_id=organization_id,
            user_id=user_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return [_to_schema(row) for row in rows], total

    def get(self, position_id: uuid.UUID) -> Position:
        row = self._repo.get(position_id)
        if row is None:
            raise NotFoundError("Position not found")
        return _to_schema(row)

    def update(self, position_id: uuid.UUID, data: PositionUpdate) -> Position:
        row = self._repo.get(position_id)
        if row is None:
            raise NotFoundError("Position not found")
        if row.status is not PositionStatus.OPEN:
            raise ValidationAppError("Only open positions can be updated.")
        if data.stop_loss is not None:
            row.stop_loss = data.stop_loss
        if data.take_profits is not None:
            row.take_profits = [
                {"price": str(tp.price), "size_fraction": tp.size_fraction}
                for tp in data.take_profits
            ]
        if data.risk_state is not None:
            row.risk_state = data.risk_state
        self._repo.add(row)
        self._record_audit(row, AuditEventType.POSITION_UPDATED, {"action": "update"})
        return _to_schema(row)

    def close_paper(self, position_id: uuid.UUID, data: ClosePaperPositionRequest) -> Position:
        row = self._repo.get(position_id)
        if row is None:
            raise NotFoundError("Position not found")
        if row.status is not PositionStatus.OPEN:
            raise ValidationAppError("Position is already closed.")
        pnl = _estimate_pnl(row, data.exit_price)
        row.realized_pnl = pnl
        row.unrealized_pnl = Decimal("0")
        row.status = PositionStatus.CLOSED
        row.closed_at = datetime.now(UTC)
        self._repo.add(row)
        self._record_audit(
            row,
            AuditEventType.POSITION_UPDATED,
            {"action": "close_paper", "exit_price": str(data.exit_price), "reason": data.reason},
        )
        return _to_schema(row)

    def _record_audit(self, row: PositionModel, event_type: AuditEventType, metadata: dict) -> None:
        self._audit.record(
            AuditRecordCreate(
                request_id="position-api",
                trace_id="position-api",
                event_type=event_type,
                resource_type="position",
                resource_id=str(row.id),
                organization_id=row.organization_id,
                user_id=row.user_id,
                actor_type=ActorType.USER,
                metadata=metadata,
            )
        )


def _estimate_pnl(row: PositionModel, exit_price: Decimal) -> Decimal:
    delta = exit_price - row.entry_price
    if row.direction is TradeDirection.SHORT:
        delta = -delta
    return delta * row.size


def _to_schema(row: PositionModel) -> Position:
    take_profits = [
        TakeProfitLevel(price=Decimal(str(tp["price"])), size_fraction=float(tp["size_fraction"]))
        for tp in (row.take_profits or [])
    ]
    return Position(
        id=row.id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        symbol=row.symbol,
        direction=row.direction,
        size=row.size,
        entry_price=row.entry_price,
        leverage=row.leverage,
        stop_loss=row.stop_loss,
        take_profits=take_profits,
        liquidation_price=row.liquidation_price,
        unrealized_pnl=row.unrealized_pnl,
        realized_pnl=row.realized_pnl,
        risk_state=row.risk_state or {},
        status=row.status,
        opened_at=row.opened_at,
        closed_at=row.closed_at,
    )
