"""Immutable backtest dataset snapshots (AT-034).

Ingest happens before snapshotting. Existing rows are reused by
``dataset_hash`` match and never updated.
"""

from __future__ import annotations

import itertools
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BacktestDataset as BacktestDatasetModel
from app.db.models import HistoricalCandle as HistoricalCandleModel
from app.providers.market_data import TIMEFRAME_SECONDS, normalize_symbol
from app.schemas.common import Timeframe
from app.services.backtest_hashing import dataset_content_hash
from app.services.historical_candle_service import HistoricalCandleService


class BacktestDatasetService:
    def __init__(
        self,
        session: Session,
        candle_service: HistoricalCandleService,
    ) -> None:
        self._session = session
        self._candles = candle_service

    def ensure_dataset(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start_date: date,
        end_date: date,
    ) -> tuple[BacktestDatasetModel, list[HistoricalCandleModel], list[str]]:
        """Ensure candles exist, then snapshot or reuse an immutable dataset row."""
        candle_rows, limitations = self._candles.ensure_candles_for_backtest(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
        )
        # Reload ordered rows after ingest so the snapshot matches persistence.
        sym = normalize_symbol(symbol)
        ex = exchange.lower()
        tf = timeframe.value
        from datetime import UTC, datetime

        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=UTC)
        rows = list(
            self._session.scalars(
                select(HistoricalCandleModel)
                .where(
                    HistoricalCandleModel.symbol == sym,
                    HistoricalCandleModel.exchange == ex,
                    HistoricalCandleModel.timeframe == tf,
                    HistoricalCandleModel.open_time >= start_dt,
                    HistoricalCandleModel.open_time <= end_dt,
                )
                .order_by(HistoricalCandleModel.open_time.asc())
            ).all()
        )
        if not rows:
            rows = candle_rows

        dataset_hash = dataset_content_hash(rows)
        existing = self._session.scalar(
            select(BacktestDatasetModel).where(BacktestDatasetModel.dataset_hash == dataset_hash)
        )
        if existing is not None:
            return existing, rows, limitations

        gap_count = self._count_gaps(rows, timeframe)
        source_counts = self._source_counts(rows)
        stale_count = sum(1 for r in rows if r.is_stale)
        dataset = BacktestDatasetModel(
            symbol=sym,
            exchange=ex,
            timeframe=tf,
            start_date=start_date,
            end_date=end_date,
            candle_count=len(rows),
            first_open_time=rows[0].open_time if rows else None,
            last_open_time=rows[-1].open_time if rows else None,
            gap_count=gap_count,
            source_counts=source_counts,
            stale_count=stale_count,
            dataset_hash=dataset_hash,
        )
        self._session.add(dataset)
        self._session.flush()
        return dataset, rows, limitations

    @staticmethod
    def _count_gaps(rows: list[HistoricalCandleModel], timeframe: Timeframe) -> int:
        if len(rows) < 2:
            return 0
        step = TIMEFRAME_SECONDS.get(timeframe, 3600)
        gaps = 0
        for prev, cur in itertools.pairwise(rows):
            delta = int((cur.open_time - prev.open_time).total_seconds())
            if delta > step:
                # Missing expected bars between prev and cur (exclusive of both ends).
                gaps += (delta // step) - 1
        return gaps

    @staticmethod
    def _source_counts(rows: list[HistoricalCandleModel]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for row in rows:
            counts[row.source] = counts.get(row.source, 0) + 1
        return dict(sorted(counts.items()))
