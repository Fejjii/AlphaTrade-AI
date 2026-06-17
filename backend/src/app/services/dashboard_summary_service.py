"""Dashboard summary aggregation (Slice 44 — paper-only, deterministic)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.common import LessonCandidateStatus, PaperAlertSeverity, PositionStatus
from app.schemas.dashboard import (
    ActivePaperValidationItem,
    AlertsLessonsSummary,
    AlertSummaryItem,
    BridgeDashboardStatus,
    DashboardSafetyStatus,
    DashboardSummary,
    MarketWatcherDashboardStatus,
    OpenPaperTradeItem,
)
from app.services.dashboard.daily_discipline import build_daily_discipline_snapshot
from app.services.dashboard.next_action import resolve_next_recommended_action
from app.services.dashboard.strategy_readiness import build_strategy_readiness
from app.services.lesson_candidate_service import LessonCandidateService
from app.services.market_watcher_bridge_service import MarketWatcherBridgeService
from app.services.market_watcher_service import MarketWatcherService
from app.services.paper_alert_service import PaperAlertService
from app.services.position_service import PositionService
from app.services.strategy_library_service import StrategyLibraryService

logger = structlog.get_logger(__name__)

_HIGH_PRIORITY = frozenset({PaperAlertSeverity.CRITICAL, PaperAlertSeverity.WARNING})
_RUNNING_PAPER = frozenset({"running", "active", "in_progress"})


class DashboardSummaryService:
    """Aggregate existing tenant data for the trader-first dashboard."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        strategies: StrategyLibraryService | None = None,
        positions: PositionService | None = None,
        alerts: PaperAlertService | None = None,
        lessons: LessonCandidateService | None = None,
        market_watcher: MarketWatcherService | None = None,
        bridge: MarketWatcherBridgeService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._strategies = strategies or StrategyLibraryService(session)
        self._positions = positions
        self._alerts = alerts or PaperAlertService(session)
        self._lessons = lessons or LessonCandidateService(session, settings=settings)
        self._market_watcher = market_watcher or MarketWatcherService(session, settings)
        self._bridge = bridge or MarketWatcherBridgeService(session, settings)

    def summarize(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> DashboardSummary:
        limitations: list[str] = []
        safety = DashboardSafetyStatus(
            execution_mode=self._settings.execution_mode.value,
            paper_only=True,
            real_trading_enabled=self._settings.real_trading_enabled,
            real_trading_disabled=not self._settings.real_trading_enabled,
        )

        daily = self._safe_section(
            "daily_discipline",
            limitations,
            lambda: build_daily_discipline_snapshot(
                self._session,
                organization_id=organization_id,
                user_id=user_id,
            ),
        )

        strategy_readiness = self._safe_section(
            "strategy_readiness",
            limitations,
            lambda: self._build_strategy_readiness(organization_id, user_id),
        )

        active_paper = self._safe_section(
            "active_paper_validations",
            limitations,
            lambda: self._active_paper_validations(organization_id, user_id),
            default=[],
        )

        open_trades = self._safe_section(
            "open_paper_trades",
            limitations,
            lambda: self._open_paper_trades(organization_id, user_id),
            default=[],
        )

        alerts_lessons = self._safe_section(
            "alerts_lessons",
            limitations,
            lambda: self._alerts_lessons_summary(organization_id, user_id),
        )

        watcher_status = self._safe_section(
            "market_watcher",
            limitations,
            lambda: self._market_watcher_status(organization_id),
        )

        bridge_status = self._safe_section(
            "bridge",
            limitations,
            lambda: self._bridge_status(organization_id),
        )

        mw_raw = None
        bridge_raw = None
        try:
            mw_raw = self._market_watcher.get_status(organization_id=organization_id)
        except Exception as exc:
            logger.warning("dashboard_market_watcher_raw_failed", error=str(exc))
        try:
            bridge_raw = self._bridge.get_status(organization_id=organization_id)
        except Exception as exc:
            logger.warning("dashboard_bridge_raw_failed", error=str(exc))

        next_action = resolve_next_recommended_action(
            real_trading_enabled=safety.real_trading_enabled,
            daily=daily,
            alerts_lessons=alerts_lessons,
            strategy_readiness=strategy_readiness,
            market_watcher=mw_raw,
            bridge=bridge_raw,
        )

        return DashboardSummary(
            safety=safety,
            daily_discipline=daily,
            strategy_readiness=strategy_readiness,
            active_paper_validations=active_paper or [],
            open_paper_trades=open_trades or [],
            alerts_lessons=alerts_lessons,
            market_watcher=watcher_status,
            bridge=bridge_status,
            next_recommended_action=next_action,
            limitations=limitations,
        )

    def _safe_section(self, name: str, limitations: list[str], builder, default=None):
        try:
            return builder()
        except Exception as exc:
            logger.warning("dashboard_section_failed", section=name, error=str(exc))
            limitations.append(f"{name} unavailable: {exc}")
            return default

    def _build_strategy_readiness(self, organization_id: uuid.UUID, user_id: uuid.UUID):
        strategies, _ = self._strategies.list_strategies(
            organization_id=organization_id,
            user_id=user_id,
            limit=100,
        )
        return build_strategy_readiness(strategies)

    def _active_paper_validations(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[ActivePaperValidationItem]:
        strategies, _ = self._strategies.list_strategies(
            organization_id=organization_id,
            user_id=user_id,
            limit=100,
        )
        items: list[ActivePaperValidationItem] = []
        for strategy in strategies:
            paper = (
                strategy.paper_validation_status.value
                if strategy.paper_validation_status
                else "not_started"
            ).lower()
            if paper in _RUNNING_PAPER:
                items.append(
                    ActivePaperValidationItem(
                        strategy_id=strategy.id,
                        name=strategy.name,
                        status="running",
                    )
                )
        return items

    def _open_paper_trades(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[OpenPaperTradeItem]:
        if self._positions is None:
            from app.services.audit_service import AuditService

            self._positions = PositionService(self._session, AuditService(self._session))
        rows, _ = self._positions.list_positions(
            organization_id=organization_id,
            user_id=user_id,
            status=PositionStatus.OPEN,
            limit=10,
        )
        return [
            OpenPaperTradeItem(
                position_id=row.id,
                symbol=row.symbol,
                direction=row.direction.value,
                unrealized_pnl=row.unrealized_pnl,
                status="open",
            )
            for row in rows
        ]

    def _alerts_lessons_summary(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> AlertsLessonsSummary:
        alert_summary = self._alerts.summary(organization_id)
        alerts_page = self._alerts.list_alerts(organization_id, limit=20, offset=0)
        high_priority = [
            AlertSummaryItem(
                alert_type=row.alert_type,
                severity=row.severity,
                message=row.message,
            )
            for row in alerts_page.items
            if row.severity in _HIGH_PRIORITY
        ][:5]

        pending, pending_total = self._lessons.list_candidates(
            organization_id=organization_id,
            user_id=user_id,
            status=LessonCandidateStatus.PENDING_REVIEW,
            limit=5,
        )
        accepted, accepted_total = self._lessons.list_accepted(
            organization_id=organization_id,
            user_id=user_id,
            limit=1,
        )
        _ = accepted
        top_pending = [f"{row.severity.value}: {row.mistake_type}" for row in pending[:3]]

        return AlertsLessonsSummary(
            unread_alerts=alert_summary.unread,
            latest_high_priority=high_priority,
            pending_lessons=pending_total,
            accepted_lessons=accepted_total,
            top_pending_lessons=top_pending,
        )

    def _market_watcher_status(self, organization_id: uuid.UUID) -> MarketWatcherDashboardStatus:
        status = self._market_watcher.get_status(organization_id=organization_id)
        fresh = 0
        if status.last_scan_at is not None:
            cutoff = datetime.now(UTC) - timedelta(hours=6)
            if status.last_scan_at >= cutoff:
                fresh = 1
        return MarketWatcherDashboardStatus(
            effective_enabled=status.effective_enabled,
            last_scan_at=status.last_scan_at.isoformat() if status.last_scan_at else None,
            fresh_observations=fresh,
        )

    def _bridge_status(self, organization_id: uuid.UUID) -> BridgeDashboardStatus:
        status = self._bridge.get_status(organization_id=organization_id)
        return BridgeDashboardStatus(
            effective_enabled=status.effective_enabled,
            last_tick_at=status.last_tick_at.isoformat() if status.last_tick_at else None,
            scans_triggered_last_tick=status.scans_triggered_last_tick,
        )
