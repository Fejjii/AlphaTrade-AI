"""Repositories for paper scheduler, alerts, and runtime history."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.db.models import (
    PaperValidationAlert,
    PaperValidationObservabilityEvent,
    PaperValidationRuntimeHistory,
    PaperValidationSampleWindow,
    PaperValidationSchedulerConfig,
)
from app.repositories.base import SQLAlchemyRepository
from app.schemas.common import PaperAlertSeverity, PaperAlertType, PaperRuntimeCycleMode


class PaperSchedulerConfigRepository(SQLAlchemyRepository[PaperValidationSchedulerConfig]):
    model = PaperValidationSchedulerConfig

    def get_or_create(self, organization_id: uuid.UUID) -> PaperValidationSchedulerConfig:
        row = self._session.scalar(
            select(PaperValidationSchedulerConfig).where(
                PaperValidationSchedulerConfig.organization_id == organization_id
            )
        )
        if row is not None:
            return row
        row = PaperValidationSchedulerConfig(organization_id=organization_id)
        self.add(row)
        return row


class PaperRuntimeHistoryRepository(SQLAlchemyRepository[PaperValidationRuntimeHistory]):
    model = PaperValidationRuntimeHistory

    def list_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        run_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperValidationRuntimeHistory], int]:
        filters = [PaperValidationRuntimeHistory.organization_id == organization_id]
        if run_id is not None:
            filters.append(PaperValidationRuntimeHistory.run_id == run_id)
        total = int(
            self._session.scalar(
                select(func.count()).select_from(PaperValidationRuntimeHistory).where(*filters)
            )
            or 0
        )
        rows = list(
            self._session.scalars(
                select(PaperValidationRuntimeHistory)
                .where(*filters)
                .order_by(PaperValidationRuntimeHistory.started_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return rows, total

    def count_recent_scans(
        self,
        organization_id: uuid.UUID,
        *,
        since: datetime,
    ) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(PaperValidationRuntimeHistory)
                .where(
                    PaperValidationRuntimeHistory.organization_id == organization_id,
                    PaperValidationRuntimeHistory.mode.in_(
                        [PaperRuntimeCycleMode.SCAN, PaperRuntimeCycleMode.SCHEDULER_TICK]
                    ),
                    PaperValidationRuntimeHistory.started_at >= since,
                )
            )
            or 0
        )


class PaperAlertRepository(SQLAlchemyRepository[PaperValidationAlert]):
    model = PaperValidationAlert

    def list_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        alert_type: PaperAlertType | None = None,
        severity: PaperAlertSeverity | None = None,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PaperValidationAlert], int]:
        filters = [PaperValidationAlert.organization_id == organization_id]
        if alert_type is not None:
            filters.append(PaperValidationAlert.alert_type == alert_type)
        if severity is not None:
            filters.append(PaperValidationAlert.severity == severity)
        if unread_only:
            filters.append(PaperValidationAlert.read_at.is_(None))
        total = int(
            self._session.scalar(
                select(func.count()).select_from(PaperValidationAlert).where(*filters)
            )
            or 0
        )
        rows = list(
            self._session.scalars(
                select(PaperValidationAlert)
                .where(*filters)
                .order_by(PaperValidationAlert.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return rows, total

    def count_unread(self, organization_id: uuid.UUID) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(PaperValidationAlert)
                .where(
                    PaperValidationAlert.organization_id == organization_id,
                    PaperValidationAlert.read_at.is_(None),
                )
            )
            or 0
        )

    def mark_read(
        self, alert_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> PaperValidationAlert | None:
        row = self._session.scalar(
            select(PaperValidationAlert).where(
                PaperValidationAlert.id == alert_id,
                PaperValidationAlert.organization_id == organization_id,
            )
        )
        if row is None:
            return None
        row.read_at = datetime.now(UTC)
        return row

    def mark_all_read(self, organization_id: uuid.UUID) -> int:
        rows = list(
            self._session.scalars(
                select(PaperValidationAlert).where(
                    PaperValidationAlert.organization_id == organization_id,
                    PaperValidationAlert.read_at.is_(None),
                )
            ).all()
        )
        now = datetime.now(UTC)
        for row in rows:
            row.read_at = now
        return len(rows)


class PaperObservabilityRepository(SQLAlchemyRepository[PaperValidationObservabilityEvent]):
    model = PaperValidationObservabilityEvent


class PaperSampleWindowRepository(SQLAlchemyRepository[PaperValidationSampleWindow]):
    model = PaperValidationSampleWindow

    def list_for_run(
        self,
        run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
    ) -> list[PaperValidationSampleWindow]:
        return list(
            self._session.scalars(
                select(PaperValidationSampleWindow)
                .where(
                    PaperValidationSampleWindow.paper_validation_run_id == run_id,
                    PaperValidationSampleWindow.organization_id == organization_id,
                )
                .order_by(PaperValidationSampleWindow.window_start.asc())
            ).all()
        )

    def count_for_run(self, run_id: uuid.UUID, *, organization_id: uuid.UUID) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(PaperValidationSampleWindow)
                .where(
                    PaperValidationSampleWindow.paper_validation_run_id == run_id,
                    PaperValidationSampleWindow.organization_id == organization_id,
                )
            )
            or 0
        )
