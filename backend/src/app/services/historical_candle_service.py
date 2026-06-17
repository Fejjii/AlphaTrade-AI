"""Historical OHLCV ingestion and storage (Slice 35)."""

from __future__ import annotations

import hashlib
import itertools
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import HistoricalCandle as HistoricalCandleModel
from app.providers.market_data import TIMEFRAME_SECONDS, MarketDataProvider, normalize_symbol
from app.repositories.historical_candles import HistoricalCandleRepository
from app.schemas.common import Timeframe
from app.schemas.historical_candles import (
    HistoricalCandle,
    HistoricalCandleList,
    HistoricalIngestRequest,
    HistoricalIngestResult,
)


class HistoricalCandleService:
    def __init__(
        self,
        session: Session,
        provider: MarketDataProvider,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._provider = provider
        self._settings = settings or get_settings()
        self._repo = HistoricalCandleRepository(session)

    def ingest(self, payload: HistoricalIngestRequest) -> HistoricalIngestResult:
        symbol = normalize_symbol(payload.symbol)
        exchange = payload.exchange.lower()
        timeframe = payload.timeframe
        start_dt = datetime.combine(payload.start_date, datetime.min.time(), tzinfo=UTC)
        end_dt = datetime.combine(payload.end_date, datetime.max.time(), tzinfo=UTC)
        if end_dt <= start_dt:
            return HistoricalIngestResult(
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                candles_stored=0,
                gaps_detected=0,
                is_complete=False,
                limitations=["end_date must be after start_date."],
            )

        step = TIMEFRAME_SECONDS.get(timeframe, 3600)
        expected = int((end_dt - start_dt).total_seconds() // step) + 1
        expected = min(max(expected, 50), 5000)

        if self._settings.provider_mode == "mock" or not self._settings.market_data_enabled:
            bars = self._generate_mock_bars(
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                start_dt=start_dt,
                count=expected,
            )
            source = "mock"
            limitations = ["Mock historical data — deterministic for tests only."]
        else:
            ohlcv = self._provider.get_ohlcv(
                symbol,
                timeframe,
                exchange=exchange,
                limit=min(expected, 1000),
            )
            bars = ohlcv.bars
            source = ohlcv.envelope.source
            limitations = []
            filtered = [b for b in bars if start_dt <= b.timestamp <= end_dt]
            if filtered:
                bars = filtered
            elif bars:
                bars = []
                limitations.append(
                    "Provider returned candles outside requested range — none stored. "
                    "Backtest window unavailable."
                )
            else:
                limitations.append("Provider returned no candles for requested range.")
            if ohlcv.envelope.fallback_used:
                limitations.append("Provider fallback used — verify data provenance.")
            if ohlcv.envelope.is_stale:
                limitations.append("Provider reported stale data.")

        models = [self._bar_to_model(bar, symbol, exchange, timeframe, source) for bar in bars]
        stored = self._repo.upsert_batch(models)
        gaps = self._count_gaps(models, step)
        is_complete = stored >= max(1, int(expected * 0.85)) and gaps <= max(2, expected // 20)

        return HistoricalIngestResult(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            candles_stored=stored,
            gaps_detected=gaps,
            is_complete=is_complete,
            freshness_note=(
                None if is_complete else "Incomplete candle coverage for requested range."
            ),
            limitations=limitations,
        )

    def get_candles(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
    ) -> HistoricalCandleList:
        sym = normalize_symbol(symbol)
        rows = self._repo.list_range(
            symbol=sym,
            exchange=exchange.lower(),
            timeframe=timeframe.value,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        step = TIMEFRAME_SECONDS.get(timeframe, 3600)
        gaps = self._count_gaps(rows, step)
        items = [self._model_to_schema(row) for row in rows]
        limitations: list[str] = []
        if gaps > 0:
            limitations.append(f"{gaps} gap(s) detected in stored candles.")
        return HistoricalCandleList(
            items=items,
            total=len(items),
            gaps_detected=gaps,
            limitations=limitations,
        )

    def ensure_candles_for_backtest(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start_date: date,
        end_date: date,
    ) -> tuple[list[HistoricalCandleModel], list[str]]:
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=UTC)
        sym = normalize_symbol(symbol)
        ex = exchange.lower()
        tf = timeframe.value
        rows = self._repo.list_range(
            symbol=sym,
            exchange=ex,
            timeframe=tf,
            start_time=start_dt,
            end_time=end_dt,
            limit=5000,
        )
        limitations: list[str] = []
        if len(rows) < 50:
            ingest = self.ingest(
                HistoricalIngestRequest(
                    symbol=sym,
                    exchange=ex,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                )
            )
            limitations.extend(ingest.limitations)
            if not ingest.is_complete:
                limitations.append("Historical data incomplete for backtest range.")
            rows = self._repo.list_range(
                symbol=sym,
                exchange=ex,
                timeframe=tf,
                start_time=start_dt,
                end_time=end_dt,
                limit=5000,
            )
        step = TIMEFRAME_SECONDS.get(timeframe, 3600)
        gaps = self._count_gaps(rows, step)
        if gaps > 0:
            limitations.append(f"{gaps} candle gap(s) — results may be unreliable.")
        stale = any(r.is_stale for r in rows)
        if stale:
            limitations.append("Stale candles present — backtest marked unreliable.")
        return rows, limitations

    def _generate_mock_bars(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start_dt: datetime,
        count: int,
    ) -> list[HistoricalCandleModel]:
        step = TIMEFRAME_SECONDS.get(timeframe, 3600)
        digest = hashlib.sha256(f"{symbol}:{timeframe}".encode()).hexdigest()
        base = Decimal(str(20000 + (int(digest[:6], 16) % 30000)))
        bars: list[HistoricalCandleModel] = []
        for i in range(count):
            open_time = start_dt + timedelta(seconds=step * i)
            close_time = open_time + timedelta(seconds=step - 1)
            trend = Decimal(str(1 + (i % 40 - 20) * 0.002))
            cycle = Decimal(str(1 + 0.01 * ((i % 15) - 7)))
            close = base * trend * cycle
            high = close * Decimal("1.008")
            low = close * Decimal("0.992")
            open_ = close * Decimal("0.999")
            bars.append(
                HistoricalCandleModel(
                    symbol=normalize_symbol(symbol),
                    exchange=exchange.lower(),
                    timeframe=timeframe.value,
                    open_time=open_time,
                    close_time=close_time,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=Decimal("100000") + Decimal(str(i * 500)),
                    source="mock",
                    is_stale=False,
                )
            )
        return bars

    @staticmethod
    def _bar_to_model(
        bar: object,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        source: str,
    ) -> HistoricalCandleModel:
        from app.providers.market_data import OHLCVBar

        if isinstance(bar, HistoricalCandleModel):
            return bar
        assert isinstance(bar, OHLCVBar)
        step = TIMEFRAME_SECONDS.get(timeframe, 3600)
        open_time = bar.timestamp
        close_time = open_time + timedelta(seconds=step - 1)
        return HistoricalCandleModel(
            symbol=symbol,
            exchange=exchange.lower(),
            timeframe=timeframe.value,
            open_time=open_time,
            close_time=close_time,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            source=source,
            is_stale=False,
        )

    @staticmethod
    def _model_to_schema(row: HistoricalCandleModel) -> HistoricalCandle:
        return HistoricalCandle(
            symbol=row.symbol,
            exchange=row.exchange,
            timeframe=Timeframe(row.timeframe),
            open_time=row.open_time,
            close_time=row.close_time,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
            source=row.source,
            is_stale=row.is_stale,
            freshness_note=row.freshness_note,
        )

    @staticmethod
    def _count_gaps(rows: list[HistoricalCandleModel], step_seconds: int) -> int:
        if len(rows) < 2:
            return 0
        gaps = 0
        for prev, curr in itertools.pairwise(rows):
            delta = (curr.open_time - prev.open_time).total_seconds()
            if delta > step_seconds * 1.5:
                gaps += 1
        return gaps
