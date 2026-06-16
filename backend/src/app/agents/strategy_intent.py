"""Detect strategy workflow questions for agent routing (Slice 34)."""

from __future__ import annotations

from app.schemas.agent import Intent


def classify_strategy_workflow(message: str) -> Intent | None:
    """Return a strategy-workflow intent when the message matches known patterns."""
    lowered = message.lower()

    if "compare" in lowered and ("trade" in lowered or "system" in lowered):
        return Intent.HUMAN_VS_SYSTEM
    if "manual level" in lowered or ("level" in lowered and "coin" in lowered):
        return Intent.MANUAL_LEVELS
    if "loss acceptable" in lowered or "loss acceptance" in lowered:
        return Intent.LOSS_ACCEPTANCE
    if "invalidation" in lowered or ("stop loss" in lowered and "?" in message):
        return Intent.INVALIDATION_QUERY
    if "position size" in lowered or "calculate size" in lowered or "sizing" in lowered:
        return Intent.POSITION_SIZE
    if "backtest" in lowered and ("next" in lowered or "needs" in lowered):
        return Intent.BACKTEST_QUEUE
    if "validated" in lowered and "strateg" in lowered:
        return Intent.STRATEGY_STATUS
    if "strategy card" in lowered or (
        "build" in lowered and "strateg" in lowered and "idea" in lowered
    ):
        return Intent.STRATEGY_CARD
    if "analyze" in lowered and "strateg" in lowered:
        return Intent.PRE_TRADE
    if "pre-trade" in lowered or "pre trade" in lowered:
        return Intent.PRE_TRADE

    return None


def is_strategy_workflow_intent(intent: Intent) -> bool:
    return intent in {
        Intent.STRATEGY_CARD,
        Intent.PRE_TRADE,
        Intent.POSITION_SIZE,
        Intent.INVALIDATION_QUERY,
        Intent.LOSS_ACCEPTANCE,
        Intent.HUMAN_VS_SYSTEM,
        Intent.MANUAL_LEVELS,
        Intent.STRATEGY_STATUS,
        Intent.BACKTEST_QUEUE,
    }
