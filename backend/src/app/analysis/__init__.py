"""Deterministic market-analysis engine (Slice 58).

Pure, side-effect-free functions for indicators, market structure, rule-based
setup detection, no-trade filters, and a transparent confidence score. No I/O,
no randomness, no wall-clock dependence: identical inputs always produce
identical outputs, which makes the engine fully testable with golden vectors.
"""

from __future__ import annotations

from app.analysis.engine import analyze
from app.analysis.types import (
    AnalysisResult,
    ConfidenceFactor,
    ConfidenceScore,
    FibonacciLevels,
    Indicators,
    Level,
    MarketStructure,
    NoTradeFilter,
    SetupDetection,
    SwingPoint,
)

__all__ = [
    "AnalysisResult",
    "ConfidenceFactor",
    "ConfidenceScore",
    "FibonacciLevels",
    "Indicators",
    "Level",
    "MarketStructure",
    "NoTradeFilter",
    "SetupDetection",
    "SwingPoint",
    "analyze",
]
