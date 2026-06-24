"""Deterministic market-scan scanner used by the background worker.

Pulls OHLCV for each configured symbol via the read-only market data provider,
runs the deterministic analysis engine, persists fired setup detections, and
returns ``(symbols_scanned, setups_detected)``. Read-only: never places orders.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy.orm import Session

from app.analysis import analyze
from app.core.config import Settings
from app.db.models import SetupDetectionRecord
from app.providers.factory import resolve_market_data_provider
from app.schemas.common import Timeframe
from app.workers.service import Scanner

logger = structlog.get_logger(__name__)


def build_market_scan_scanner(
    settings: Settings,
    *,
    timeframe: Timeframe = Timeframe.H1,
    limit: int = 200,
) -> Scanner:
    """Build a scanner over ``settings.market_watcher_default_symbols``."""
    market_data = resolve_market_data_provider(settings)
    symbols = list(settings.market_watcher_default_symbols)

    def _scan(session: Session) -> tuple[int, int]:
        detected = 0
        for symbol in symbols:
            try:
                ohlcv = market_data.get_ohlcv(symbol, timeframe, limit=limit)
            except Exception as exc:  # one bad symbol must not fail the cycle
                logger.warning("worker_scan_symbol_failed", symbol=symbol, error=str(exc)[:200])
                continue
            result = analyze(symbol, timeframe.value, list(ohlcv.bars))
            for detection in result.detections:
                if not detection.detected:
                    continue
                detected += 1
                session.add(
                    SetupDetectionRecord(
                        symbol=symbol,
                        timeframe=timeframe.value,
                        setup_name=detection.name,
                        direction=detection.direction,
                        confidence=result.confidence.score,
                        reason=detection.reason,
                        detected_metrics=detection.metrics,
                        detected_at=datetime.now(UTC),
                    )
                )
        return len(symbols), detected

    return _scan
