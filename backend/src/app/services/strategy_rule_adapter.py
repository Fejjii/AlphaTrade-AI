"""Parse strategy card rules into machine-evaluable backtest parameters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.schemas.common import StrategyId, TradeDirection
from app.schemas.strategy_library import StrategyCard


@dataclass(frozen=True)
class ParsedStrategyRules:
    machine_readable: bool
    limitation: str | None
    direction: TradeDirection
    entry_mode: str | None
    stop_pct: Decimal
    tp_r_multiples: tuple[Decimal, ...]
    use_runner: bool
    matched_tokens: tuple[str, ...]


_MACHINE_TOKENS = (
    "pullback",
    "ema",
    "rsi",
    "breakout",
    "break above",
    "break below",
    "swing low",
    "swing high",
    "prior high",
    "prior low",
    "support",
    "resistance",
    "tp1",
    "tp2",
    "tp3",
    "stop",
    "invalidation",
    "trail",
    "runner",
)

_SETUP_DEFAULTS: dict[StrategyId, ParsedStrategyRules] = {
    StrategyId.HTF_TREND_PULLBACK: ParsedStrategyRules(
        machine_readable=True,
        limitation=None,
        direction=TradeDirection.LONG,
        entry_mode="pullback_ema",
        stop_pct=Decimal("0.02"),
        tp_r_multiples=(Decimal("1"), Decimal("2"), Decimal("3")),
        use_runner=True,
        matched_tokens=("setup:htf_trend_pullback",),
    ),
    StrategyId.LIQUIDITY_SWEEP_REVERSAL: ParsedStrategyRules(
        machine_readable=True,
        limitation=None,
        direction=TradeDirection.LONG,
        entry_mode="liquidity_sweep",
        stop_pct=Decimal("0.015"),
        tp_r_multiples=(Decimal("1"), Decimal("2")),
        use_runner=False,
        matched_tokens=("setup:liquidity_sweep_reversal",),
    ),
}


def _extract_stop_pct(texts: list[str]) -> Decimal | None:
    joined = " ".join(texts).lower()
    pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", joined)
    if pct_match:
        return Decimal(pct_match.group(1)) / Decimal("100")
    if "tight" in joined:
        return Decimal("0.01")
    if "wide" in joined:
        return Decimal("0.03")
    return None


def _extract_tp_multiples(texts: list[str]) -> tuple[Decimal, ...]:
    joined = " ".join(texts).lower()
    multiples: list[Decimal] = []
    for label, value in (("tp1", Decimal("1")), ("tp2", Decimal("2")), ("tp3", Decimal("3"))):
        if label in joined or f"{label} at" in joined:
            multiples.append(value)
    if multiples:
        return tuple(multiples)
    if "prior high" in joined or "take profit" in joined:
        return (Decimal("1"), Decimal("2"))
    return (Decimal("1"), Decimal("2"), Decimal("3"))


def parse_strategy_rules(card: StrategyCard, setup_type: StrategyId) -> ParsedStrategyRules:
    """Return machine-readable rule parameters or a limitation message."""
    if setup_type in _SETUP_DEFAULTS:
        base = _SETUP_DEFAULTS[setup_type]
        stop = _extract_stop_pct(card.stop_loss + card.invalidation) or base.stop_pct
        tps = _extract_tp_multiples(card.take_profit_plan) or base.tp_r_multiples
        return ParsedStrategyRules(
            machine_readable=True,
            limitation=None,
            direction=base.direction,
            entry_mode=base.entry_mode,
            stop_pct=stop,
            tp_r_multiples=tps,
            use_runner=any("trail" in r.lower() or "runner" in r.lower() for r in card.runner_plan)
            or base.use_runner,
            matched_tokens=base.matched_tokens,
        )

    corpus = " ".join(
        card.entry_conditions
        + card.confirmation_conditions
        + card.invalidation
        + card.stop_loss
        + card.take_profit_plan
    ).lower()
    matched = [token for token in _MACHINE_TOKENS if token in corpus]
    if len(matched) < 2:
        return ParsedStrategyRules(
            machine_readable=False,
            limitation=(
                "Strategy rules are not machine-readable. Structure entry, stop, and take-profit "
                "using keywords like pullback, EMA, RSI, TP1, stop %, "
                "or use a supported setup type."
            ),
            direction=TradeDirection.LONG,
            entry_mode=None,
            stop_pct=Decimal("0.02"),
            tp_r_multiples=(Decimal("1"), Decimal("2")),
            use_runner=False,
            matched_tokens=tuple(matched),
        )

    entry_mode = "pullback_ema" if "pullback" in corpus or "ema" in corpus else "breakout"
    if "break" in corpus:
        entry_mode = "breakout"
    stop = _extract_stop_pct(card.stop_loss + card.invalidation) or Decimal("0.02")
    tps = _extract_tp_multiples(card.take_profit_plan)
    return ParsedStrategyRules(
        machine_readable=True,
        limitation=None,
        direction=TradeDirection.SHORT if "short" in corpus else TradeDirection.LONG,
        entry_mode=entry_mode,
        stop_pct=stop,
        tp_r_multiples=tps,
        use_runner=any("trail" in r.lower() or "runner" in r.lower() for r in card.runner_plan),
        matched_tokens=tuple(matched),
    )
