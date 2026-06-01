"""Strategy module interface — deterministic evaluate(), typed I/O."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.schemas.common import StrategyId, Timeframe, TradeDirection
from app.schemas.strategy import EntryZone, StrategySignal


@dataclass(frozen=True)
class StrategyEvaluationInput:
    """Inputs for deterministic strategy evaluation (synthetic or live data)."""

    symbol: str
    timeframe: Timeframe
    close: Decimal
    volume: Decimal
    funding_rate: Decimal | None = None
    rsi: float | None = None
    ema_fast: Decimal | None = None
    ema_slow: Decimal | None = None
    htf_trend: TradeDirection | None = None
    liquidity_sweep_detected: bool = False
    momentum_exhausted: bool = False
    at_confluence_level: bool = False
    green_day_active: bool = False
    stress_score: int | None = None
    tags: dict[str, bool] = field(default_factory=dict)
    data_is_live: bool = False
    data_is_stale: bool = False
    data_fallback_used: bool = True


class StrategyModule(ABC):
    """A single MVP strategy module with a deterministic ``evaluate`` method."""

    strategy_id: StrategyId

    @abstractmethod
    def evaluate(self, data: StrategyEvaluationInput) -> StrategySignal | None:
        """Return a structured signal or ``None`` when no setup is detected."""

    def _signal(
        self,
        data: StrategyEvaluationInput,
        *,
        direction: TradeDirection,
        confidence: float,
        invalidation: str,
        evidence: list[str],
        risk_notes: list[str],
        entry_zone: EntryZone | None = None,
    ) -> StrategySignal:
        return StrategySignal(
            strategy_id=self.strategy_id,
            symbol=data.symbol,
            timeframe=data.timeframe,
            direction=direction,
            confidence=confidence,
            entry_zone=entry_zone,
            invalidation=invalidation,
            evidence=evidence,
            risk_notes=risk_notes,
            timestamp=datetime.now(UTC),
        )
