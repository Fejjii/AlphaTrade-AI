"""Paper validation observability and runtime history (Slice 40)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog
from sqlalchemy.orm import Session

from app.db.models import (
    PaperValidationObservabilityEvent as ObservabilityEventModel,
)
from app.db.models import PaperValidationRuntimeHistory as RuntimeHistoryModel
from app.guardrails.redaction import redact_mapping, redact_text
from app.repositories.paper_scheduler import (
    PaperObservabilityRepository,
    PaperRuntimeHistoryRepository,
)
from app.schemas.common import (
    PaperObservabilityEventType,
    PaperRuntimeCycleMode,
    PaperRuntimeCycleStatus,
)
from app.schemas.paper_scheduler import PaperRuntimeHistoryRecord

logger = structlog.get_logger("paper_observability")


@dataclass
class _HistoryBuilder:
    organization_id: uuid.UUID
    mode: PaperRuntimeCycleMode
    run_id: uuid.UUID | None = None
    strategy_id: uuid.UUID | None = None
    symbol: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    _start_perf: float = field(default_factory=time.perf_counter)
    signals_created: int = 0
    trades_opened: int = 0
    trades_closed: int = 0
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data_freshness: str | None = None
    reason: str | None = None
    error_type: str | None = None
    error_message: str | None = None

    def complete(
        self,
        status: PaperRuntimeCycleStatus,
        *,
        reason: str | None = None,
    ) -> RuntimeHistoryModel:
        latency_ms = int((time.perf_counter() - self._start_perf) * 1000)
        return RuntimeHistoryModel(
            organization_id=self.organization_id,
            run_id=self.run_id,
            strategy_id=self.strategy_id,
            symbol=self.symbol,
            mode=self.mode,
            started_at=self.started_at,
            completed_at=datetime.now(UTC),
            status=status,
            reason=reason or self.reason,
            signals_created=self.signals_created,
            trades_opened=self.trades_opened,
            trades_closed=self.trades_closed,
            blockers=self.blockers or None,
            warnings=self.warnings or None,
            data_freshness=self.data_freshness,
            latency_ms=latency_ms,
            error_type=self.error_type,
            error_message=redact_text(self.error_message) if self.error_message else None,
        )


class PaperObservabilityService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._history = PaperRuntimeHistoryRepository(session)
        self._events = PaperObservabilityRepository(session)

    def start_history(
        self,
        *,
        organization_id: uuid.UUID,
        mode: PaperRuntimeCycleMode,
        run_id: uuid.UUID | None = None,
        strategy_id: uuid.UUID | None = None,
        symbol: str | None = None,
    ) -> _HistoryBuilder:
        return _HistoryBuilder(
            organization_id=organization_id,
            mode=mode,
            run_id=run_id,
            strategy_id=strategy_id,
            symbol=symbol,
        )

    def record_history(
        self,
        builder: _HistoryBuilder,
        status: PaperRuntimeCycleStatus,
        **kwargs,
    ) -> RuntimeHistoryModel:
        row = builder.complete(status, **kwargs)
        self._history.add(row)
        return row

    def emit(
        self,
        *,
        organization_id: uuid.UUID,
        event_type: PaperObservabilityEventType,
        run_id: uuid.UUID | None = None,
        strategy_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> None:
        redacted = redact_mapping(metadata or {})
        self._events.add(
            ObservabilityEventModel(
                organization_id=organization_id,
                event_type=event_type,
                run_id=run_id,
                strategy_id=strategy_id,
                metadata_json=redacted or None,
            )
        )
        logger.info(
            event_type.value,
            organization_id=str(organization_id),
            run_id=str(run_id) if run_id else None,
            strategy_id=str(strategy_id) if strategy_id else None,
            **redacted,
        )

    def list_history(
        self,
        organization_id: uuid.UUID,
        *,
        run_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperRuntimeHistoryRecord], int]:
        rows, total = self._history.list_for_org(
            organization_id, run_id=run_id, limit=limit, offset=offset
        )
        return [self._to_schema(r) for r in rows], total

    @staticmethod
    def _to_schema(row: RuntimeHistoryModel) -> PaperRuntimeHistoryRecord:
        return PaperRuntimeHistoryRecord(
            id=row.id,
            organization_id=row.organization_id,
            run_id=row.run_id,
            strategy_id=row.strategy_id,
            symbol=row.symbol,
            mode=row.mode,
            started_at=row.started_at,
            completed_at=row.completed_at,
            status=row.status,
            reason=row.reason,
            signals_created=row.signals_created,
            trades_opened=row.trades_opened,
            trades_closed=row.trades_closed,
            blockers=list(row.blockers or []),
            warnings=list(row.warnings or []),
            data_freshness=row.data_freshness,
            latency_ms=row.latency_ms,
            error_type=row.error_type,
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
