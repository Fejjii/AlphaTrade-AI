"""Resolve structured rules into backtest parameters (Slice 36)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.schemas.common import (
    EntryTriggerType,
    ExitRuleType,
    RuleEngineSource,
    StrategyId,
)
from app.schemas.strategy_library import StrategyCard
from app.schemas.structured_rules import StructuredRules
from app.services.strategy_rule_adapter import ParsedStrategyRules, parse_strategy_rules

_ENTRY_MODE_MAP = {
    EntryTriggerType.EMA_PULLBACK: "pullback_ema",
    EntryTriggerType.BREAKOUT: "breakout",
    EntryTriggerType.LIQUIDITY_SWEEP: "liquidity_sweep",
    EntryTriggerType.RECLAIM: "pullback_ema",
    EntryTriggerType.FAILED_BREAKOUT: "breakout",
    EntryTriggerType.RSI_THRESHOLD: "pullback_ema",
    EntryTriggerType.VOLUME_CONFIRMATION: "breakout",
    EntryTriggerType.TREND_ALIGNMENT: "pullback_ema",
}


@dataclass(frozen=True)
class ResolvedRules:
    rules: ParsedStrategyRules
    engine_source: RuleEngineSource


def structured_rules_to_parsed(rules: StructuredRules) -> ParsedStrategyRules:
    """Convert structured rule blocks to engine parameters."""
    entry = rules.entry_rules[0]
    entry_mode = _ENTRY_MODE_MAP.get(entry.trigger_type, "pullback_ema")
    direction = entry.direction

    stop_pct = Decimal("0.02")
    tp_multiples: tuple[Decimal, ...] = (Decimal("1"), Decimal("2"), Decimal("3"))
    use_runner = False

    for exit_rule in rules.exit_rules:
        if exit_rule.rule_type == ExitRuleType.FIXED_STOP and exit_rule.value is not None:
            stop_pct = (
                exit_rule.value / Decimal("100")
                if exit_rule.value < Decimal("1")
                else exit_rule.value
            )
        elif exit_rule.rule_type == ExitRuleType.ATR_STOP:
            stop_pct = Decimal("0.015")
        elif exit_rule.rule_type == ExitRuleType.SWING_STOP:
            stop_pct = Decimal("0.02")
        elif exit_rule.rule_type == ExitRuleType.TP_MULTIPLE and exit_rule.r_multiple is not None:
            tp_multiples = (exit_rule.r_multiple,)
        elif exit_rule.rule_type == ExitRuleType.PARTIAL_TP:
            tp_multiples = (Decimal("1"), Decimal("2"))
        elif exit_rule.rule_type == ExitRuleType.RUNNER_STRUCTURE_BREAK:
            use_runner = True

    return ParsedStrategyRules(
        machine_readable=True,
        limitation=None,
        direction=direction,
        entry_mode=entry_mode,
        stop_pct=stop_pct,
        tp_r_multiples=tp_multiples,
        use_runner=use_runner,
        matched_tokens=(f"structured:{entry.trigger_type.value}",),
    )


def resolve_backtest_rules(
    card: StrategyCard,
    setup_type: StrategyId,
    structured: StructuredRules | None,
) -> ResolvedRules:
    """Prefer structured rules, then text adapter, then setup defaults."""
    if structured is not None and structured.entry_rules:
        try:
            parsed = structured_rules_to_parsed(structured)
            return ResolvedRules(rules=parsed, engine_source=RuleEngineSource.STRUCTURED)
        except Exception:
            pass

    parsed = parse_strategy_rules(card, setup_type)
    if parsed.machine_readable:
        if parsed.matched_tokens and parsed.matched_tokens[0].startswith("setup:"):
            return ResolvedRules(rules=parsed, engine_source=RuleEngineSource.DEFAULT_SETUP)
        return ResolvedRules(rules=parsed, engine_source=RuleEngineSource.ADAPTER)

    return ResolvedRules(
        rules=parsed,
        engine_source=RuleEngineSource.UNSUPPORTED,
    )
