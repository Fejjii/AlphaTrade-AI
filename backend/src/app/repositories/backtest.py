"""Backtest run persistence."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.db.models import BacktestRun
from app.repositories.base import SQLAlchemyRepository
from app.schemas.common import BacktestRunStatus

_ACTIVE_STATUSES: tuple[BacktestRunStatus, ...] = (
    BacktestRunStatus.QUEUED,
    BacktestRunStatus.RUNNING,
    BacktestRunStatus.CANCEL_REQUESTED,
)


class BacktestRunRepository(SQLAlchemyRepository[BacktestRun]):
    model = BacktestRun

    def list_for_strategy(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BacktestRun], int]:
        filters = [
            BacktestRun.strategy_id == strategy_id,
            BacktestRun.organization_id == organization_id,
        ]
        count_stmt = select(func.count()).select_from(BacktestRun).where(*filters)
        list_stmt = (
            select(BacktestRun)
            .where(*filters)
            .order_by(BacktestRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        total = int(self._session.scalar(count_stmt) or 0)
        return list(self._session.scalars(list_stmt).all()), total

    def get_scoped(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> BacktestRun | None:
        stmt = select(BacktestRun).where(
            BacktestRun.id == run_id,
            BacktestRun.organization_id == organization_id,
        )
        return self._session.scalar(stmt)

    def get_by_idempotency_key(
        self,
        *,
        organization_id: uuid.UUID,
        idempotency_key: str,
    ) -> BacktestRun | None:
        stmt = select(BacktestRun).where(
            BacktestRun.organization_id == organization_id,
            BacktestRun.idempotency_key == idempotency_key,
        )
        return self._session.scalar(stmt)

    def count_active_for_org(self, organization_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(BacktestRun)
            .where(
                BacktestRun.organization_id == organization_id,
                BacktestRun.status.in_(_ACTIVE_STATUSES),
            )
        )
        return int(self._session.scalar(stmt) or 0)

    def claim_queued(self, run_id: uuid.UUID) -> BacktestRun | None:
        """Claim a QUEUED run for execution (QUEUED → RUNNING)."""
        run = self._session.get(BacktestRun, run_id)
        if run is None or run.status != BacktestRunStatus.QUEUED:
            return None
        run.status = BacktestRunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        self._session.flush()
        return run

    def next_queued(self) -> BacktestRun | None:
        """Oldest QUEUED run across orgs (worker drain — at most one per cycle)."""
        stmt = (
            select(BacktestRun)
            .where(BacktestRun.status == BacktestRunStatus.QUEUED)
            .order_by(BacktestRun.created_at.asc())
            .limit(1)
        )
        return self._session.scalar(stmt)

    def cancel_probe(self, run_id: uuid.UUID) -> tuple[BacktestRunStatus, datetime | None] | None:
        """Lightweight status + cancel_requested_at read for should_cancel."""
        stmt = select(BacktestRun.status, BacktestRun.cancel_requested_at).where(
            BacktestRun.id == run_id
        )
        row = self._session.execute(stmt).one_or_none()
        if row is None:
            return None
        status: BacktestRunStatus = row[0]
        cancel_at: datetime | None = row[1]
        return status, cancel_at


# Re-export for type checkers that import the active-status set.
ACTIVE_BACKTEST_STATUSES: Sequence[BacktestRunStatus] = _ACTIVE_STATUSES
