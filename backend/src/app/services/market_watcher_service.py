"""Read-only market watcher foundation (Slice 41/72 — no execution)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import ExecutionMode, Settings, get_settings
from app.db.models import MarketWatcherObservation as ObservationModel
from app.db.models import PaperValidationRun, WatchlistItem
from app.guardrails.redaction import redact_text
from app.providers.factory import resolve_market_data_provider
from app.providers.market_data import OHLCVBar
from app.repositories.market_watcher import MarketWatcherObservationRepository
from app.repositories.paper_validation import PaperValidationRunRepository
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    MarketWatcherObservationStatus,
    PaperAlertSource,
    PaperObservabilityEventType,
    PaperValidationStatus,
)
from app.schemas.market_watcher import (
    SCAN_CONFIRM_PHRASE,
    MarketWatcherCandidate,
    MarketWatcherObservation,
    MarketWatcherScanRequest,
    MarketWatcherScanResult,
    MarketWatcherStatus,
    MarketWatcherSummary,
    PaginatedMarketWatcherHistory,
    PaginatedMarketWatcherObservations,
)
from app.services.audit_service import AuditService
from app.services.market_data_service import MarketDataService
from app.services.market_watcher_scanner import (
    SUPPORTED_SYMBOLS,
    SUPPORTED_TIMEFRAMES,
    ScanCandidate,
    decimal_metrics,
    detect_candidates,
    normalize_symbols,
    normalize_timeframes,
    parse_timeframe,
)
from app.services.paper_alert_service import PaperAlertService
from app.services.paper_observability_service import PaperObservabilityService
from app.workers.repository import WorkerHeartbeatRepository

logger = structlog.get_logger("market_watcher")


@dataclass
class _LastScanState:
    scanned_at: datetime
    status: str
    alerts_created: int
    error: str | None


class MarketWatcherService:
    """Read-only market scanning — never places orders or calls trading APIs."""

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        *,
        audit_service: AuditService | None = None,
        market_data: MarketDataService | None = None,
        alert_service: PaperAlertService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._observations = MarketWatcherObservationRepository(session)
        self._runs = PaperValidationRunRepository(session)
        self._audit = audit_service or AuditService(session)
        self._observability = PaperObservabilityService(session)
        self._alerts = alert_service or PaperAlertService(session)
        if market_data is None:
            provider = resolve_market_data_provider(self._settings)
            self._market_data = MarketDataService(provider)
        else:
            self._market_data = market_data
        self._scan_history: dict[uuid.UUID, list[MarketWatcherScanResult]] = {}
        self._last_scan_state: dict[uuid.UUID, _LastScanState] = {}

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

    def get_summary(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MarketWatcherSummary:
        now = datetime.now(UTC)
        worker_running = self._worker_running()
        last = self._last_scan_state.get(organization_id)
        warnings: list[str] = []
        readiness: str = "ready"

        if self._settings.real_trading_enabled:
            readiness = "blocked"
            warnings.append("Real trading is enabled — manual scan blocked.")
        elif self._settings.execution_mode != ExecutionMode.PAPER:
            readiness = "blocked"
            warnings.append("Execution mode is not paper — manual scan blocked.")
        elif worker_running and self._settings.market_watcher_enabled:
            warnings.append("Worker heartbeat detected while scanner automation is enabled.")

        if last and last.status == "degraded":
            readiness = "degraded" if readiness == "ready" else readiness
            warnings.append("Last scan completed with provider degradation.")

        manual_available = (
            not self._settings.real_trading_enabled
            and self._settings.execution_mode == ExecutionMode.PAPER
        )

        return MarketWatcherSummary(
            scanner_enabled=self._settings.market_watcher_enabled,
            manual_scan_available=manual_available,
            worker_enabled=self._settings.worker_enabled,
            worker_running=worker_running,
            symbols_supported=list(SUPPORTED_SYMBOLS),
            timeframes_supported=list(SUPPORTED_TIMEFRAMES),
            last_scan_at=last.scanned_at if last else None,
            last_scan_status=last.status if last else None,  # type: ignore[arg-type]
            last_scan_alerts_created=last.alerts_created if last else 0,
            last_scan_error=last.error if last else None,
            paper_only=True,
            readiness=readiness,  # type: ignore[arg-type]
            warnings=warnings,
            generated_at=now,
        )

    def scan(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        request: MarketWatcherScanRequest,
    ) -> MarketWatcherScanResult:
        now = datetime.now(UTC)
        decisions: list[str] = []

        if request.confirm != SCAN_CONFIRM_PHRASE:
            result = self._blocked_result(
                now,
                decisions=["Confirmation phrase required for manual scan."],
                error="confirmation_required",
            )
            self._record_last_scan(organization_id, result)
            return result

        if self._settings.real_trading_enabled:
            result = self._blocked_result(
                now,
                decisions=["Real trading is enabled — manual scan blocked."],
                error="real_trading_enabled",
            )
            self._record_last_scan(organization_id, result)
            return result

        if self._settings.execution_mode != ExecutionMode.PAPER:
            result = self._blocked_result(
                now,
                decisions=["Execution mode is not paper — manual scan blocked."],
                error="execution_mode_not_paper",
            )
            self._record_last_scan(organization_id, result)
            return result

        symbols = normalize_symbols(request.symbols)
        timeframes = normalize_timeframes(request.timeframes)
        if not symbols:
            result = self._blocked_result(
                now,
                decisions=["No supported symbols in request."],
                error="invalid_symbols",
            )
            self._record_last_scan(organization_id, result)
            return result
        if not timeframes:
            result = self._blocked_result(
                now,
                decisions=["No supported timeframes in request."],
                error="invalid_timeframes",
            )
            self._record_last_scan(organization_id, result)
            return result

        candidates: list[MarketWatcherCandidate] = []
        alerts_created = 0
        alerts_deduped = 0
        observations_created = 0
        setup_signals: list[str] = []
        provider_failures = 0
        pairs_scanned = 0

        for symbol in symbols:
            for timeframe_str in timeframes:
                tf = parse_timeframe(timeframe_str)
                if tf is None:
                    continue
                pairs_scanned += 1
                try:
                    ohlcv = self._market_data.get_ohlcv(symbol, tf, exchange="binance", limit=100)
                    bars = [
                        OHLCVBar(
                            open=b.open,
                            high=b.high,
                            low=b.low,
                            close=b.close,
                            volume=b.volume,
                            timestamp=b.timestamp,
                        )
                        for b in ohlcv.bars
                    ]
                    observed_at = ohlcv.meta.timestamp or now
                    latest_price = bars[-1].close if bars else None
                    row = ObservationModel(
                        organization_id=organization_id,
                        symbol=symbol,
                        exchange="binance",
                        timeframe=tf.value,
                        observed_at=observed_at,
                        price=Decimal(str(latest_price)) if latest_price is not None else None,
                        volume=Decimal(str(bars[-1].volume)) if bars else None,
                        data_freshness=ohlcv.meta.source,
                        status=(
                            MarketWatcherObservationStatus.STALE
                            if ohlcv.meta.is_stale
                            else MarketWatcherObservationStatus.FRESH
                        ),
                        notes="Slice 72 read-only scanner observation.",
                    )
                    self._observations.add(row)
                    observations_created += 1

                    for raw in detect_candidates(symbol=symbol, timeframe=tf.value, bars=bars):
                        candidate = self._materialize_candidate(
                            organization_id=organization_id,
                            user_id=user_id,
                            raw=raw,
                            dry_run=request.dry_run,
                        )
                        candidates.append(candidate)
                        if candidate.deduped:
                            alerts_deduped += 1
                        elif candidate.created_alert_id is not None:
                            alerts_created += 1
                            setup_signals.append(
                                f"{symbol} {tf.value}: {raw.condition} → in-app alert"
                            )
                            row.created_alert_id = candidate.created_alert_id
                except Exception as exc:
                    provider_failures += 1
                    redacted = redact_text(str(exc))[:200]
                    logger.warning(
                        "market_watcher_scan_pair_failed",
                        symbol=symbol,
                        timeframe=timeframe_str,
                        error=redacted,
                    )
                    decisions.append(f"{symbol} {timeframe_str}: scan degraded ({redacted}).")
                    row = ObservationModel(
                        organization_id=organization_id,
                        symbol=symbol,
                        exchange="binance",
                        timeframe=tf.value,
                        observed_at=now,
                        price=None,
                        volume=None,
                        data_freshness="error",
                        status=MarketWatcherObservationStatus.UNAVAILABLE,
                        notes=redacted,
                    )
                    self._observations.add(row)
                    observations_created += 1

        status: str = "ok"
        if provider_failures and pairs_scanned > 0:
            status = "degraded"

        if request.dry_run:
            decisions.append(f"Dry-run preview: {len(candidates)} candidate(s), no alerts created.")
        else:
            decisions.append(
                f"Scan complete: {alerts_created} in-app alert(s), {alerts_deduped} deduped."
            )

        self._observability.emit(
            organization_id=organization_id,
            event_type=PaperObservabilityEventType.MARKET_WATCHER_SCAN,
            metadata={
                "symbols_scanned": len(symbols),
                "timeframes": timeframes,
                "pairs_scanned": pairs_scanned,
                "observations_created": observations_created,
                "candidates": len(candidates),
                "alerts_created": alerts_created,
                "dry_run": request.dry_run,
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
                result=AuditResult.SUCCESS if status == "ok" else AuditResult.FAILURE,
                severity=AuditSeverity.INFO,
                metadata={
                    "action": "market_watcher_scan",
                    "dry_run": request.dry_run,
                    "symbols_scanned": len(symbols),
                    "pairs_scanned": pairs_scanned,
                    "candidates": len(candidates),
                    "alerts_created": alerts_created,
                    "paper_only": True,
                },
            )
        )
        result = MarketWatcherScanResult(
            scanned_at=now,
            env_enabled=self._settings.market_watcher_enabled,
            effective_enabled=True,
            symbols_scanned=len(symbols),
            observations_created=observations_created,
            setup_signals=setup_signals,
            decisions=decisions,
            paper_only=True,
            dry_run=request.dry_run,
            status=status,  # type: ignore[arg-type]
            candidates=candidates,
            alerts_created=alerts_created,
            alerts_deduped=alerts_deduped,
            error=None if status == "ok" else "provider_degraded",
        )
        self._record_history(organization_id, result)
        self._record_last_scan(organization_id, result)
        return result

    def _materialize_candidate(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        raw: ScanCandidate,
        dry_run: bool,
    ) -> MarketWatcherCandidate:
        if dry_run:
            return MarketWatcherCandidate(
                symbol=raw.symbol,
                timeframe=raw.timeframe,
                condition=raw.condition,
                message=raw.message,
                severity=raw.severity.value,
                metrics=decimal_metrics(raw.metrics),
            )

        created = self._alerts.create(
            organization_id=organization_id,
            user_id=user_id,
            alert_type=raw.alert_type,
            severity=raw.severity,
            message=raw.message,
            metadata={
                "source": PaperAlertSource.MARKET_WATCHER.value,
                "condition": raw.condition,
                "symbol": raw.symbol,
                "timeframe": raw.timeframe,
                "metrics": decimal_metrics(raw.metrics),
            },
            dedup_key=raw.dedup_key,
            source=PaperAlertSource.MARKET_WATCHER,
        )
        if created is None:
            return MarketWatcherCandidate(
                symbol=raw.symbol,
                timeframe=raw.timeframe,
                condition=raw.condition,
                message=raw.message,
                severity=raw.severity.value,
                metrics=decimal_metrics(raw.metrics),
                deduped=True,
            )
        return MarketWatcherCandidate(
            symbol=raw.symbol,
            timeframe=raw.timeframe,
            condition=raw.condition,
            message=raw.message,
            severity=raw.severity.value,
            metrics=decimal_metrics(raw.metrics),
            created_alert_id=created.id,
        )

    def _blocked_result(
        self,
        now: datetime,
        *,
        decisions: list[str],
        error: str,
    ) -> MarketWatcherScanResult:
        return MarketWatcherScanResult(
            scanned_at=now,
            env_enabled=self._settings.market_watcher_enabled,
            effective_enabled=False,
            symbols_scanned=0,
            observations_created=0,
            setup_signals=[],
            decisions=decisions,
            paper_only=True,
            dry_run=True,
            status="blocked",
            candidates=[],
            alerts_created=0,
            alerts_deduped=0,
            error=redact_text(error),
        )

    def _record_last_scan(
        self,
        organization_id: uuid.UUID,
        result: MarketWatcherScanResult,
    ) -> None:
        self._last_scan_state[organization_id] = _LastScanState(
            scanned_at=result.scanned_at,
            status=result.status,
            alerts_created=result.alerts_created,
            error=result.error,
        )

    def _worker_running(self) -> bool:
        if not self._settings.worker_enabled:
            return False
        heartbeat = WorkerHeartbeatRepository(self._session).get_by_name(self._settings.worker_name)
        if heartbeat is None:
            return False
        last_beat = heartbeat.last_beat_at
        if last_beat.tzinfo is None:
            last_beat = last_beat.replace(tzinfo=UTC)
        seconds_since = (datetime.now(UTC) - last_beat).total_seconds()
        liveness_window = self._settings.worker_scan_interval_seconds * 3
        return (
            seconds_since <= liveness_window
            and heartbeat.status != "error"
            and not heartbeat.paused
        )

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
