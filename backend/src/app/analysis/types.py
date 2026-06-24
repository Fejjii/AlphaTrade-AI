"""Typed value objects produced by the analysis engine."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SwingPoint:
    """A confirmed pivot high or low."""

    index: int
    price: float
    kind: str  # "high" | "low"


@dataclass(frozen=True)
class Level:
    """A clustered support or resistance level."""

    price: float
    kind: str  # "support" | "resistance"
    touches: int
    strength: float  # 0..1, normalized by touch count


@dataclass(frozen=True)
class FibonacciLevels:
    """Fibonacci retracement levels for the latest dominant swing."""

    direction: str  # "up" | "down"
    swing_high: float
    swing_low: float
    levels: dict[str, float] = field(default_factory=dict)  # ratio label -> price


@dataclass(frozen=True)
class MarketStructure:
    """Trend classification from the sequence of swing labels."""

    trend: str  # "uptrend" | "downtrend" | "range"
    last_label: str | None  # "HH" | "HL" | "LH" | "LL" | None
    swing_points: tuple[SwingPoint, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Indicators:
    """Deterministic indicator snapshot for the latest bar."""

    sma_fast: float | None
    sma_slow: float | None
    ema_fast: float | None
    ema_slow: float | None
    rsi: float | None
    macd: float | None
    macd_signal: float | None
    macd_hist: float | None
    atr: float | None
    vwap: float | None
    volume: float | None
    volume_avg: float | None
    volume_ratio: float | None
    volatility: float | None
    funding_rate: float | None


@dataclass(frozen=True)
class SetupDetection:
    """Result of a single rule-based setup detector."""

    name: str
    detected: bool
    direction: str | None  # "long" | "short" | None
    reason: str
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class NoTradeFilter:
    """A guard that, when ``blocked`` is true, vetoes new entries."""

    name: str
    blocked: bool
    reason: str


@dataclass(frozen=True)
class ConfidenceFactor:
    """One weighted input to the confidence score, with its contribution."""

    name: str
    weight: float
    score: float  # 0..1
    contribution: float  # weight * score, before normalization


@dataclass(frozen=True)
class ConfidenceScore:
    """Transparent 0..100 confidence with per-factor breakdown."""

    score: float
    factors: tuple[ConfidenceFactor, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AnalysisResult:
    """Complete deterministic analysis for one symbol/timeframe."""

    symbol: str
    timeframe: str
    bar_count: int
    indicators: Indicators
    structure: MarketStructure
    support_levels: tuple[Level, ...]
    resistance_levels: tuple[Level, ...]
    fibonacci: FibonacciLevels | None
    detections: tuple[SetupDetection, ...]
    no_trade_filters: tuple[NoTradeFilter, ...]
    no_trade: bool
    confidence: ConfidenceScore
