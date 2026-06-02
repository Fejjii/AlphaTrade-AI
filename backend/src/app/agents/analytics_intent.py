"""Detect trading analytics questions for agent routing."""

from __future__ import annotations

_ANALYTICS_PHRASES = (
    "setup",
    "setups",
    "mistake",
    "mistakes",
    "emotion",
    "emotions",
    "discipline",
    "risk rule",
    "risk rules",
    "improve",
    "improvement",
    "weakest",
    "overtrade",
    "overtrading",
    "green day",
    "daily loss",
    "journal",
    "analytics",
    "performance",
    "win rate",
    "losing trades",
)


def is_analytics_message(message: str) -> bool:
    lowered = message.lower()
    return any(phrase in lowered for phrase in _ANALYTICS_PHRASES)
