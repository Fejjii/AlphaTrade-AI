"""Walk-forward sample windows from closed paper trades (Slice 40)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import PaperValidationSampleWindow as SampleWindowModel
from app.repositories.paper_runtime import PaperTradeRepository
from app.repositories.paper_scheduler import PaperSampleWindowRepository
from app.schemas.common import PaperTradeStatus
from app.schemas.paper_scheduler import PaperValidationSampleWindow
from app.services.paper_validation_promotion import compute_max_drawdown

WINDOW_DAYS = 7


class PaperSampleWindowService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._windows = PaperSampleWindowRepository(session)
        self._trades = PaperTradeRepository(session)

    def refresh_for_run(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> list[PaperValidationSampleWindow]:
        rows, _ = self._trades.list_for_run(
            run_id,
            organization_id=organization_id,
            status=PaperTradeStatus.CLOSED,
            limit=500,
        )
        if not rows:
            return []

        closed = sorted(
            [r for r in rows if r.exit_time],
            key=lambda r: r.exit_time or datetime.min.replace(tzinfo=UTC),
        )
        if not closed:
            return []

        start = closed[0].exit_time
        end = closed[-1].exit_time
        assert start is not None and end is not None

        windows: list[SampleWindowModel] = []
        cursor = start
        while cursor <= end:
            window_end = cursor + timedelta(days=WINDOW_DAYS)
            in_window = [r for r in closed if r.exit_time and cursor <= r.exit_time < window_end]
            if in_window:
                windows.append(
                    self._build_window(run_id, organization_id, cursor, window_end, in_window)
                )
            cursor = window_end

        existing = self._windows.list_for_run(run_id, organization_id=organization_id)
        for old in existing:
            self._session.delete(old)
        for w in windows:
            self._windows.add(w)
        return [self._to_schema(w) for w in windows]

    def list_for_run(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> list[PaperValidationSampleWindow]:
        rows = self._windows.list_for_run(run_id, organization_id=organization_id)
        return [self._to_schema(r) for r in rows]

    def count_windows(self, run_id: uuid.UUID, *, organization_id: uuid.UUID) -> int:
        return self._windows.count_for_run(run_id, organization_id=organization_id)

    def _build_window(
        self,
        run_id: uuid.UUID,
        organization_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
        trades: list,
    ) -> SampleWindowModel:
        pnls = [t.net_pnl or Decimal("0") for t in trades]
        wins = [p for p in pnls if p > 0]
        net = sum(pnls, Decimal("0"))
        count = len(trades)
        equity = Decimal("10000")
        curve = [equity]
        for pnl in pnls:
            equity += pnl
            curve.append(equity)
        max_dd = compute_max_drawdown(curve)
        win_rate = len(wins) / count if count else 0.0
        expectancy = net / Decimal(str(count)) if count else Decimal("0")
        recommendation = "continue"
        data_quality = "ok"
        if count < 3:
            recommendation = "insufficient_data"
            data_quality = "sparse"
        elif expectancy <= 0:
            recommendation = "improve"
        elif max_dd > 25:
            recommendation = "restrict"
        return SampleWindowModel(
            paper_validation_run_id=run_id,
            organization_id=organization_id,
            window_start=window_start,
            window_end=window_end,
            trades_count=count,
            win_rate=win_rate,
            net_pnl=net,
            max_drawdown=max_dd,
            expectancy=expectancy,
            recommendation=recommendation,
            data_quality=data_quality,
        )

    @staticmethod
    def _to_schema(row: SampleWindowModel) -> PaperValidationSampleWindow:
        return PaperValidationSampleWindow(
            id=row.id,
            paper_validation_run_id=row.paper_validation_run_id,
            organization_id=row.organization_id,
            window_start=row.window_start,
            window_end=row.window_end,
            trades_count=row.trades_count,
            win_rate=row.win_rate,
            net_pnl=str(row.net_pnl),
            max_drawdown=row.max_drawdown,
            expectancy=str(row.expectancy),
            recommendation=row.recommendation,
            data_quality=row.data_quality,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
