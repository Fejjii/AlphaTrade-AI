"""Read-only market watcher foundation (Slice 41 — no execution)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import MarketWatcherObservation as ObservationModel
from app.db.models import PaperValidationRun, WatchlistItem
from app.providers.factory import resolve_market_data_provider
from app.repositories.market_watcher import MarketWatcherObservationRepository
from app.repositories.paper_validation import PaperValidationRunRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    MarketWatcherObservationStatus,
    PaperObservabilityEventType,
    PaperValidationStatus,
    Timeframe,
)
from app.schemas.market_watcher import (
    MarketWatcherObservation,
    MarketWatcherScanResult,
    MarketWatcherStatus,
    PaginatedMarketWatcherHistory,
    PaginatedMarketWatcherObservations,
)
from app.services.audit_service import AuditService
from app.services.market_data_service import MarketDataService
from app.services.paper_observability_service import PaperObservabilityService

logger = structlog.get_logger("market_watcher")


class MarketWatcherService:
    """Read-only market scanning — never places orders or calls trading APIs."""

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        *,
        audit_service: AuditService | None = None,
        market_data: MarketDataService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._observations = MarketWatcherObservationRepository(session)
        self._runs = PaperValidationRunRepository(session)
        self._audit = audit_service or AuditService(session)
        self._observability = PaperObservabilityService(session)
        if market_data is None:
            provider = resolve_market_data_provider(self._settings)
            self._market_data = MarketDataService(provider)
        else:
            self._market_data = market_data
        self._scan_history: dict[uuid.UUID, list[MarketWatcherScanResult]] = {}

    def get_status(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MarketWatcherStatus:
        symbols = self._resolve_symbols(organization_id, user_id)
        last_scan = self._observations.latest_for_org(organization_id)
        if last_scan is None:
            history = self._scan_history.get(organization_id, [])
            if history:
                last_scan = history[-1].scanned_at
        return MarketWatcherStatus(
            env_enabled=self._settings.market_watcher_enabled,
            effective_enabled=self._settings.market_watcher_enabled,
            watched_symbols=symbols,
            last_scan_at=last_scan,
            paper_only=True,
            real_trading_enabled=self._settings.real_trading_enabled,
        )

    def scan(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MarketWatcherScanResult:
        now = datetime.now(UTC)
        decisions: list[str] = []
        setup_signals: list[str] = []

        if not self._settings.market_watcher_enabled:
            decisions.append("Market watcher disabled: MARKET_WATCHER_ENABLED=false.")
            result = MarketWatcherScanResult(
                scanned_at=now,
                env_enabled=False,
                effective_enabled=False,
                symbols_scanned=0,
                observations_created=0,
                setup_signals=setup_signals,
                decisions=decisions,
                paper_only=True,
            )
            self._record_history(organization_id, result)
            return result

        symbols = self._resolve_symbols(organization_id, user_id)
        observations_created = 0
        stale_minutes = self._settings.market_watcher_stale_data_max_age_minutes

        for symbol in symbols:
            try:
                ticker = self._market_data.get_ticker(symbol, exchange="binance")
                meta = ticker.meta
                observed_at = meta.timestamp or now
                age_minutes = (now - observed_at).total_seconds() / 60 if observed_at else 999
                if meta.is_stale or age_minutes > stale_minutes:
                    status = MarketWatcherObservationStatus.STALE
                    freshness = f"stale_{int(age_minutes)}m"
                elif not meta.is_live and meta.provider_name == "mock":
                    status = MarketWatcherObservationStatus.UNAVAILABLE
                    freshness = "mock_unavailable"
                else:
                    status = MarketWatcherObservationStatus.FRESH
                    freshness = meta.source

                run_id, strategy_id = self._active_run_for_symbol(organization_id, symbol=symbol)
                notes = None
                if run_id is not None:
                    notes = "Active paper validation run — eligible for scan decision."
                    setup_signals.append(f"{symbol}: paper validation run active")

                row = ObservationModel(
                    organization_id=organization_id,
                    symbol=symbol,
                    exchange="binance",
                    timeframe=Timeframe.H4.value,
                    observed_at=observed_at,
                    price=Decimal(str(ticker.last_price)),
                    volume=Decimal(str(ticker.volume_24h)) if ticker.volume_24h else None,
                    data_freshness=freshness,
                    status=status,
                    related_strategy_id=strategy_id,
                    related_paper_validation_run_id=run_id,
                    notes=notes,
                )
                self._observations.add(row)
                observations_created += 1
            except Exception as exc:
                logger.warning(
                    "market_watcher_symbol_failed",
                    symbol=symbol,
                    error=str(exc),
                )
                row = ObservationModel(
                    organization_id=organization_id,
                    symbol=symbol,
                    exchange="binance",
                    timeframe=Timeframe.H4.value,
                    observed_at=now,
                    price=None,
                    volume=None,
                    data_freshness="error",
                    status=MarketWatcherObservationStatus.UNAVAILABLE,
                    notes=str(exc)[:200],
                )
                self._observations.add(row)
                observations_created += 1
                decisions.append(f"{symbol}: observation unavailable.")

        self._observability.emit(
            organization_id=organization_id,
            event_type=PaperObservabilityEventType.MARKET_WATCHER_SCAN,
            metadata={
                "symbols_scanned": len(symbols),
                "observations_created": observations_created,
                "paper_only": True,
            },
        )
        self._audit.record(
            AuditRecordCreate(
                request_id=f"market-watcher-scan-{organization_id}",
                trace_id=str(uuid.uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                event_type=AuditEventType.PAPER_VALIDATION_RUNTIME,
                resource_type="market_watcher",
                resource_id=str(organization_id),
                actor_type=ActorType.USER,
                result=AuditResult.SUCCESS,
                severity=AuditSeverity.INFO,
                metadata={
                    "action": "market_watcher_scan",
                    "symbols_scanned": len(symbols),
                    "observations_created": observations_created,
                    "paper_only": True,
                },
            )
        )
        result = MarketWatcherScanResult(
            scanned_at=now,
            env_enabled=True,
            effective_enabled=True,
            symbols_scanned=len(symbols),
            observations_created=observations_created,
            setup_signals=setup_signals,
            decisions=decisions or [f"Scanned {len(symbols)} symbol(s) read-only."],
            paper_only=True,
        )
        self._record_history(organization_id, result)
        return result

    def list_observations(
        self,
        organization_id: uuid.UUID,
        *,
        symbol: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedMarketWatcherObservations:
        rows, total = self._observations.list_for_org(
            organization_id, symbol=symbol, limit=limit, offset=offset
        )
        return PaginatedMarketWatcherObservations(
            items=[self._to_schema(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def list_history(self, organization_id: uuid.UUID) -> PaginatedMarketWatcherHistory:
        items = self._scan_history.get(organization_id, [])
        return PaginatedMarketWatcherHistory(items=items, total=len(items))

    def _resolve_symbols(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> list[str]:
        rows = list(
            self._session.scalars(
                select(WatchlistItem).where(
                    WatchlistItem.organization_id == organization_id,
                    WatchlistItem.user_id == user_id,
                    WatchlistItem.enabled.is_(True),
                )
            ).all()
        )
        symbols = [row.symbol for row in rows]
        if not symbols:
            symbols = list(self._settings.market_watcher_default_symbols)
        return sorted(set(symbols))

    def _active_run_for_symbol(
        self,
        organization_id: uuid.UUID,
        *,
        symbol: str,
    ) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        row = self._session.scalar(
            select(PaperValidationRun)
            .where(
                PaperValidationRun.organization_id == organization_id,
                PaperValidationRun.status.in_(
                    [PaperValidationStatus.IN_PROGRESS, PaperValidationStatus.NOT_STARTED]
                ),
            )
            .order_by(PaperValidationRun.started_at.desc())
            .limit(1)
        )
        if row is None:
            return None, None
        config = row.config or {}
        config_symbol = str(config.get("symbol") or config.get("assumptions", {}).get("symbol", ""))
        if config_symbol and config_symbol != symbol:
            return None, None
        return row.id, row.strategy_id

    def _record_history(self, organization_id: uuid.UUID, result: MarketWatcherScanResult) -> None:
        history = self._scan_history.setdefault(organization_id, [])
        history.append(result)
        if len(history) > 20:
            del history[0]

    @staticmethod
    def _to_schema(row: ObservationModel) -> MarketWatcherObservation:
        return MarketWatcherObservation(
            id=row.id,
            organization_id=row.organization_id,
            symbol=row.symbol,
            exchange=row.exchange,
            timeframe=row.timeframe,
            observed_at=row.observed_at,
            price=row.price,
            volume=row.volume,
            data_freshness=row.data_freshness,
            status=row.status,
            related_strategy_id=row.related_strategy_id,
            related_paper_validation_run_id=row.related_paper_validation_run_id,
            notes=row.notes,
            created_alert_id=row.created_alert_id,
            created_at=row.created_at,
        )
