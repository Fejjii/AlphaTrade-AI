"""Keyword-assisted draft of structured rules from plain English (Slice 36)."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.schemas.common import (
    EntryTriggerType,
    ExitRuleType,
    NoTradeRuleType,
    Timeframe,
    TradeDirection,
)
from app.schemas.strategy_pattern_spec import (
    FIRST_SLICE_CONTEXT_TF,
    FIRST_SLICE_KIND,
    FIRST_SLICE_TRIGGER_TF,
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

_EXPLICIT_NUMBER = re.compile(r"(-?\d+(?:\.\d+)?)")


def _extract_named_number(text: str, *labels: str) -> Decimal | None:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*[:=]?\s*{_EXPLICIT_NUMBER.pattern}", text, re.I)
        if match:
            try:
                return Decimal(match.group(1))
            except InvalidOperation:
                return None
    return None


class StructureFromTextService:
    """Draft structured rules — deterministic validation decides testability."""

    def draft(self, request: StructureFromTextRequest) -> StructureFromTextResponse:
        return self.draft_preview(request)

    def draft_preview(self, request: StructureFromTextRequest) -> StructureFromTextResponse:
        text = request.text.lower()
        limitations = [
            "Draft rules are keyword-assisted — review and edit before backtesting.",
            "Deterministic validation decides testability, not the draft generator.",
            "This preview does not write a strategy version or compiled setup.",
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
        pattern_spec, pattern_errors = self._pattern_spec_preview(text)
        challenge_notes = self._challenge_notes(text, draft, pattern_errors)
        return StructureFromTextResponse(
            draft=draft,
            validation=StructuredRulesValidation(valid=valid, errors=errors, warnings=warnings),
            limitations=limitations,
            pattern_spec_draft=pattern_spec,
            pattern_spec_errors=pattern_errors,
            challenge_notes=challenge_notes,
            is_preview=True,
            persists_strategy=False,
        )

    def _pattern_spec_preview(self, text: str) -> tuple[dict | None, list[str]]:
        """Emit FirstSliceAuthoredPatternSpec only when every threshold is explicit.

        Canonical first-slice constants are never copied in. Missing fields fail closed.
        """
        wants_first_slice = (
            FIRST_SLICE_KIND in text
            or ("liquidity sweep" in text and "cvd" in text)
            or ("bearish" in text and "sweep" in text and "imbalance" in text)
        )
        if not wants_first_slice:
            return None, []
        missing: list[str] = []
        if FIRST_SLICE_TRIGGER_TF not in text:
            missing.append("trigger_timeframe (15m must be stated)")
        if FIRST_SLICE_CONTEXT_TF not in text:
            missing.append("context_timeframe (4h must be stated)")
        if (
            _extract_named_number(
                text, "resistance_distance_atr", "resistance atr", "resistance_distance"
            )
            is None
        ):
            missing.append("resistance_distance_atr_threshold")
        if (
            _extract_named_number(text, "sweep_threshold_atr", "sweep atr", "sweep_threshold")
            is None
        ):
            missing.append("sweep_threshold_atr")
        if _extract_named_number(text, "volume_ratio", "volume ratio") is None:
            missing.append("volume_ratio_threshold")
        if (
            _extract_named_number(
                text, "aggressive_sell_imbalance", "sell imbalance", "imbalance_threshold"
            )
            is None
        ):
            missing.append("aggressive_sell_imbalance_threshold")
        if _extract_named_number(text, "invalidation atr", "atr_multiple") is None:
            missing.append("invalidation.atr_multiple")
        if _extract_named_number(text, "tick_multiple", "tick multiple") is None:
            missing.append("invalidation.tick_multiple")
        # Fail closed: never invent the remaining first-slice identity fields.
        missing.extend(
            [
                "sequence",
                "trigger_atr",
                "context_atr",
                "required_finality",
            ]
        )
        return None, missing

    def _challenge_notes(
        self,
        text: str,
        draft: StructuredRules,
        pattern_errors: list[str],
    ) -> list[str]:
        notes: list[str] = []
        if "always" in text or "guaranteed" in text:
            notes.append("Avoid absolute language. Rules must stay testable and conservative.")
        if not draft.no_trade_rules:
            notes.append("Consider an explicit no-trade filter (session, funding, or daily loss).")
        if pattern_errors:
            notes.append(
                "First-slice pattern_spec stays omitted until every threshold is stated. "
                "The compiler will not invent values."
            )
        if "activate" in text or "go live" in text or "enable watcher" in text:
            notes.append(
                "Conversational drafts cannot activate Watcher, Telegram, or live trading."
            )
        return notes
