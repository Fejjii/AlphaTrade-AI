"""Manual chart level service (Slice 33)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import ManualChartLevel as ManualChartLevelModel
from app.repositories.manual_levels import ManualChartLevelRepository
from app.schemas.manual_levels import (
    ManualChartLevel,
    ManualChartLevelCreate,
    ManualChartLevelUpdate,
)


class ManualLevelService:
    def __init__(self, session: Session) -> None:
        self._repo = ManualChartLevelRepository(session)

    def create(self, payload: ManualChartLevelCreate) -> ManualChartLevel:
        entity = ManualChartLevelModel(
            organization_id=payload.organization_id,
            user_id=payload.user_id,
            symbol=str(payload.symbol),
            exchange=payload.exchange,
            timeframe=payload.timeframe.value if payload.timeframe else None,
            level_type=payload.level_type,
            price=payload.price,
            price_low=payload.price_low,
            price_high=payload.price_high,
            label=payload.label,
            notes=payload.notes,
            enabled=payload.enabled,
        )
        self._repo.add(entity)
        return ManualChartLevel.model_validate(entity, from_attributes=True)

    def list_levels(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        symbol: str | None = None,
        exchange: str | None = None,
        enabled_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ManualChartLevel], int]:
        rows, total = self._repo.list_scoped(
            organization_id=organization_id,
            user_id=user_id,
            symbol=symbol,
            exchange=exchange,
            enabled_only=enabled_only,
            limit=limit,
            offset=offset,
        )
        items = [ManualChartLevel.model_validate(row, from_attributes=True) for row in rows]
        return items, total

    def get(
        self,
        level_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ManualChartLevel:
        row = self._repo.get_scoped(level_id, organization_id=organization_id, user_id=user_id)
        if row is None:
            raise NotFoundError("Manual level not found.")
        return ManualChartLevel.model_validate(row, from_attributes=True)

    def update(
        self,
        level_id: uuid.UUID,
        payload: ManualChartLevelUpdate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ManualChartLevel:
        row = self._repo.get_scoped(level_id, organization_id=organization_id, user_id=user_id)
        if row is None:
            raise NotFoundError("Manual level not found.")
        data = payload.model_dump(exclude_unset=True)
        if "symbol" in data and data["symbol"] is not None:
            row.symbol = str(data["symbol"])
        if "timeframe" in data and data["timeframe"] is not None:
            row.timeframe = data["timeframe"].value
        for key in (
            "exchange",
            "level_type",
            "price",
            "price_low",
            "price_high",
            "label",
            "notes",
            "enabled",
        ):
            if key in data:
                setattr(row, key, data[key])
        return ManualChartLevel.model_validate(row, from_attributes=True)

    def delete(
        self,
        level_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        row = self._repo.get_scoped(level_id, organization_id=organization_id, user_id=user_id)
        if row is None:
            raise NotFoundError("Manual level not found.")
        self._repo.delete(row)
