"""Historical candle persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.db.models import HistoricalCandle
from app.repositories.base import SQLAlchemyRepository


class HistoricalCandleRepository(SQLAlchemyRepository[HistoricalCandle]):
    model = HistoricalCandle

    def upsert_batch(self, candles: list[HistoricalCandle]) -> int:
        stored = 0
        for candle in candles:
            existing = self._session.scalar(
                select(HistoricalCandle).where(
                    HistoricalCandle.symbol == candle.symbol,
                    HistoricalCandle.exchange == candle.exchange,
                    HistoricalCandle.timeframe == candle.timeframe,
                    HistoricalCandle.open_time == candle.open_time,
                )
            )
            if existing is None:
                self._session.add(candle)
                stored += 1
        return stored

    def list_range(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 5000,
    ) -> list[HistoricalCandle]:
        filters = [
            HistoricalCandle.symbol == symbol,
            HistoricalCandle.exchange == exchange,
            HistoricalCandle.timeframe == timeframe,
        ]
        if start_time is not None:
            filters.append(HistoricalCandle.open_time >= start_time)
        if end_time is not None:
            filters.append(HistoricalCandle.open_time <= end_time)
        stmt = (
            select(HistoricalCandle)
            .where(*filters)
            .order_by(HistoricalCandle.open_time.asc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def count_range(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        filters = [
            HistoricalCandle.symbol == symbol,
            HistoricalCandle.exchange == exchange,
            HistoricalCandle.timeframe == timeframe,
        ]
        if start_time is not None:
            filters.append(HistoricalCandle.open_time >= start_time)
        if end_time is not None:
            filters.append(HistoricalCandle.open_time <= end_time)
        stmt = select(func.count()).select_from(HistoricalCandle).where(*filters)
        return int(self._session.scalar(stmt) or 0)
