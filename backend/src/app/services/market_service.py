"""Watchlist business logic."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import WatchlistItem as WatchlistModel
from app.repositories.watchlist import WatchlistRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import ActorType, AuditEventType, StrategyId, Timeframe
from app.schemas.market import WatchlistItem, WatchlistItemCreate, WatchlistItemUpdate
from app.services.audit_service import AuditService
from app.services.workflow_validation import (
    validate_exchange,
    validate_strategy_ids,
    validate_timeframes,
)


class MarketService:
    """Tenant-scoped watchlist management."""

    def __init__(self, session: Session, audit_service: AuditService) -> None:
        self._repo = WatchlistRepository(session)
        self._audit = audit_service

    def create(self, data: WatchlistItemCreate) -> WatchlistItem:
        exchange = validate_exchange(data.exchange)
        timeframes = validate_timeframes(data.timeframes)
        strategy_ids = validate_strategy_ids(data.strategy_ids)
        row = WatchlistModel(
            organization_id=data.organization_id,
            user_id=data.user_id,
            symbol=str(data.symbol),
            exchange=exchange,
            timeframes=[tf.value for tf in timeframes],
            strategy_ids=[sid.value for sid in strategy_ids],
            enabled=data.enabled,
        )
        self._repo.add(row)
        self._audit_event(
            event_type=AuditEventType.TOOL_CALLED,
            organization_id=data.organization_id,
            user_id=data.user_id,
            resource_type="watchlist_item",
            resource_id=str(row.id),
            metadata={"action": "create", "symbol": str(data.symbol), "exchange": exchange},
        )
        return _to_schema(row)

    def list_items(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[WatchlistItem], int]:
        rows, total = self._repo.list_items(
            organization_id=organization_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        return [_to_schema(row) for row in rows], total

    def update(
        self,
        item_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        data: WatchlistItemUpdate,
    ) -> WatchlistItem:
        row = self._repo.get_scoped(item_id, organization_id=organization_id, user_id=user_id)
        if row is None:
            raise NotFoundError("Watchlist item not found")
        if data.timeframes is not None:
            row.timeframes = [tf.value for tf in validate_timeframes(data.timeframes)]
        if data.strategy_ids is not None:
            row.strategy_ids = [sid.value for sid in validate_strategy_ids(data.strategy_ids)]
        if data.enabled is not None:
            row.enabled = data.enabled
        self._repo.add(row)
        self._audit_event(
            event_type=AuditEventType.TOOL_CALLED,
            organization_id=organization_id,
            user_id=user_id,
            resource_type="watchlist_item",
            resource_id=str(row.id),
            metadata={"action": "update"},
        )
        return _to_schema(row)

    def delete(
        self,
        item_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        row = self._repo.get_scoped(item_id, organization_id=organization_id, user_id=user_id)
        if row is None:
            raise NotFoundError("Watchlist item not found")
        self._repo.delete(row)
        self._audit_event(
            event_type=AuditEventType.TOOL_CALLED,
            organization_id=organization_id,
            user_id=user_id,
            resource_type="watchlist_item",
            resource_id=str(item_id),
            metadata={"action": "delete"},
        )

    def _audit_event(self, **kwargs: object) -> None:
        self._audit.record(
            AuditRecordCreate(
                request_id="watchlist-api",
                trace_id="watchlist-api",
                event_type=kwargs["event_type"],  # type: ignore[arg-type]
                resource_type=str(kwargs["resource_type"]),
                resource_id=str(kwargs["resource_id"]),
                organization_id=kwargs["organization_id"],  # type: ignore[arg-type]
                user_id=kwargs["user_id"],  # type: ignore[arg-type]
                actor_type=ActorType.USER,
                metadata=kwargs.get("metadata", {}),  # type: ignore[arg-type]
            )
        )


def _to_schema(row: WatchlistModel) -> WatchlistItem:
    return WatchlistItem(
        id=row.id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        symbol=row.symbol,
        exchange=row.exchange,
        timeframes=[Timeframe(tf) for tf in row.timeframes],
        strategy_ids=[StrategyId(sid) for sid in row.strategy_ids],
        enabled=row.enabled,
        created_at=row.created_at,
    )
