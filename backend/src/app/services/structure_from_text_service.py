"""Keyword-assisted draft of structured rules from plain English (Slice 36)."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.common import (
    EntryTriggerType,
    ExitRuleType,
    NoTradeRuleType,
    Timeframe,
    TradeDirection,
)
from app.schemas.structured_rules import (
    EntryRuleBlock,
    ExitRuleBlock,
    NoTradeRuleBlock,
    StructuredRules,
    StructuredRulesValidation,
    StructureFromTextRequest,
    StructureFromTextResponse,
)
from app.services.strategy_testability_service import validate_structured_rules


class StructureFromTextService:
    """Draft structured rules — deterministic validation decides testability."""

    def draft(self, request: StructureFromTextRequest) -> StructureFromTextResponse:
        text = request.text.lower()
        limitations = [
            "Draft rules are keyword-assisted — review and edit before backtesting.",
            "Deterministic validation decides testability, not the draft generator.",
        ]
        entry_type = EntryTriggerType.EMA_PULLBACK
        if "breakout" in text or "break above" in text:
            entry_type = EntryTriggerType.BREAKOUT
        elif "liquidity sweep" in text or "sweep" in text:
            entry_type = EntryTriggerType.LIQUIDITY_SWEEP
        elif "reclaim" in text:
            entry_type = EntryTriggerType.RECLAIM
        elif "rsi" in text:
            entry_type = EntryTriggerType.RSI_THRESHOLD
        elif "volume" in text:
            entry_type = EntryTriggerType.VOLUME_CONFIRMATION

        direction = TradeDirection.SHORT if "short" in text else TradeDirection.LONG
        tf = Timeframe.H4
        for candidate in Timeframe:
            if candidate.value in text:
                tf = candidate
                break

        exit_rules: list[ExitRuleBlock] = []
        if "atr" in text and "stop" in text:
            exit_rules.append(ExitRuleBlock(rule_type=ExitRuleType.ATR_STOP))
        elif "swing" in text and "stop" in text:
            exit_rules.append(ExitRuleBlock(rule_type=ExitRuleType.SWING_STOP))
        else:
            pct = Decimal("2")
            if "%" in text:
                import re

                match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
                if match:
                    pct = Decimal(match.group(1))
            exit_rules.append(ExitRuleBlock(rule_type=ExitRuleType.FIXED_STOP, value=pct))

        if "tp1" in text or "take profit" in text or "1r" in text:
            exit_rules.append(
                ExitRuleBlock(rule_type=ExitRuleType.TP_MULTIPLE, r_multiple=Decimal("1"))
            )
        if "tp2" in text or "2r" in text:
            exit_rules.append(
                ExitRuleBlock(rule_type=ExitRuleType.TP_MULTIPLE, r_multiple=Decimal("2"))
            )
        if not any(r.rule_type == ExitRuleType.TP_MULTIPLE for r in exit_rules):
            exit_rules.append(
                ExitRuleBlock(rule_type=ExitRuleType.TP_MULTIPLE, r_multiple=Decimal("1"))
            )
        if "runner" in text or "trail" in text:
            exit_rules.append(ExitRuleBlock(rule_type=ExitRuleType.RUNNER_STRUCTURE_BREAK))

        no_trade: list[NoTradeRuleBlock] = []
        if "funding" in text:
            no_trade.append(NoTradeRuleBlock(rule_type=NoTradeRuleType.HIGH_FUNDING))
        if "weekend" in text:
            no_trade.append(NoTradeRuleBlock(rule_type=NoTradeRuleType.WEEKEND_CHOP))
        if "daily loss" in text:
            no_trade.append(NoTradeRuleBlock(rule_type=NoTradeRuleType.DAILY_LOSS_LOCK))

        draft = StructuredRules(
            primary_timeframe=tf,
            entry_rules=[EntryRuleBlock(trigger_type=entry_type, direction=direction)],
            exit_rules=exit_rules,
            no_trade_rules=no_trade,
        )
        valid, errors, warnings = validate_structured_rules(draft)
        return StructureFromTextResponse(
            draft=draft,
            validation=StructuredRulesValidation(valid=valid, errors=errors, warnings=warnings),
            limitations=limitations,
        )
