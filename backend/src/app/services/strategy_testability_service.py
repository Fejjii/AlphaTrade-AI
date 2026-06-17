"""Deterministic strategy testability scoring (Slice 36)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.common import TestabilityBand
from app.schemas.strategy_library import StrategyCard
from app.schemas.strategy_testability import MissingRuleField, StrategyTestability
from app.schemas.structured_rules import StructuredRules


def validate_structured_rules(rules: StructuredRules) -> tuple[bool, list[str], list[str]]:
    """Validate structured rules for backtest readiness."""
    errors: list[str] = []
    warnings: list[str] = []
    if not rules.entry_rules:
        errors.append("At least one entry rule is required.")
    has_stop = any(
        r.rule_type.value in {"fixed_stop", "atr_stop", "swing_stop"} for r in rules.exit_rules
    )
    if not has_stop:
        errors.append("At least one stop exit rule is required.")
    has_tp = any(
        r.rule_type.value in {"tp_multiple", "tp_price_levels", "partial_tp"}
        for r in rules.exit_rules
    )
    if not has_tp:
        warnings.append("No take-profit exit rule — backtest may use defaults.")
    if rules.primary_timeframe is None:
        warnings.append("Primary timeframe not set — will use backtest assumptions.")
    return len(errors) == 0, errors, warnings


class StrategyTestabilityService:
    """Score whether a strategy can be backtested mechanically."""

    def __init__(self, session: Session) -> None:
        self._strategies = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)

    def score(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> StrategyTestability:
        strategy = self._strategies.get_scoped(
            strategy_id, organization_id=organization_id, user_id=user_id
        )
        if strategy is None:
            raise NotFoundError("Strategy not found.")
        version = self._versions.latest(strategy_id)
        card = StrategyCard.model_validate(version.card) if version else None
        structured = self._load_structured_rules(version)
        missing = self._detect_missing(card, structured)
        score = self._compute_score(card, structured, missing)
        band = self._band(score)
        ready = score >= 70 and not any(m.severity == "required" for m in missing)
        limitations: list[str] = []
        if score < 70:
            limitations.append("Strategy needs structured rules before reliable backtest v1.")
        unsupported, ambiguous, suggested = self._analyze_rule_quality(structured)
        not_ready_reason = None
        if not ready:
            if missing:
                not_ready_reason = f"Missing: {', '.join(m.label for m in missing[:3])}"
            elif unsupported:
                not_ready_reason = f"Unsupported rule types: {', '.join(unsupported[:3])}"
            else:
                not_ready_reason = "Structured rules incomplete for backtest v1."
        return StrategyTestability(
            strategy_id=strategy_id,
            score=score,
            band=band,
            ready_for_backtest=ready,
            missing_fields=missing,
            unsupported_rule_types=unsupported,
            ambiguous_conditions=ambiguous,
            not_backtestable_reason=not_ready_reason,
            suggested_edits=suggested,
            has_structured_rules=structured is not None,
            structured_rules=structured,
            limitations=limitations,
        )

    def validate_structured(self, rules: StructuredRules) -> tuple[bool, list[str], list[str]]:
        return validate_structured_rules(rules)

    def _load_structured_rules(self, version: object | None) -> StructuredRules | None:
        if version is None:
            return None
        raw = getattr(version, "structured_rules", None)
        if not raw:
            return None
        try:
            return StructuredRules.model_validate(raw)
        except Exception:
            return None

    def _detect_missing(
        self,
        card: StrategyCard | None,
        structured: StructuredRules | None,
    ) -> list[MissingRuleField]:
        missing: list[MissingRuleField] = []
        if structured is None:
            missing.append(
                MissingRuleField(
                    field_key="structured_rules",
                    label="Structured rule blocks",
                    severity="required",
                )
            )
        else:
            if not structured.entry_rules:
                missing.append(
                    MissingRuleField(field_key="entry_trigger", label="Entry trigger missing")
                )
            has_stop = any(
                r.rule_type.value in {"fixed_stop", "atr_stop", "swing_stop"}
                for r in structured.exit_rules
            )
            if not has_stop:
                missing.append(MissingRuleField(field_key="stop_loss", label="Stop loss missing"))
            has_tp = any(
                r.rule_type.value in {"tp_multiple", "tp_price_levels", "partial_tp"}
                for r in structured.exit_rules
            )
            if not has_tp:
                missing.append(MissingRuleField(field_key="tp_plan", label="TP plan missing"))
            if not structured.no_trade_rules:
                missing.append(
                    MissingRuleField(
                        field_key="no_trade_rules",
                        label="No-trade rules missing",
                        severity="optional",
                    )
                )
            if structured.primary_timeframe is None:
                missing.append(MissingRuleField(field_key="timeframe", label="Timeframe missing"))

        if card is not None:
            if not card.invalidation:
                missing.append(
                    MissingRuleField(field_key="invalidation", label="Invalidation missing")
                )
            if structured is None:
                corpus = " ".join(
                    card.entry_conditions + card.stop_loss + card.take_profit_plan
                ).lower()
                if (
                    sum(1 for t in ("pullback", "ema", "rsi", "breakout", "stop") if t in corpus)
                    < 2
                ):
                    missing.append(
                        MissingRuleField(
                            field_key="rule_conditions_vague",
                            label="Rule conditions too vague",
                        )
                    )

        return missing

    def _compute_score(
        self,
        card: StrategyCard | None,
        structured: StructuredRules | None,
        missing: list[MissingRuleField],
    ) -> int:
        if structured is not None:
            valid, _, _ = validate_structured_rules(structured)
            base = 75 if valid else 55
            base += min(15, len(structured.entry_rules) * 5)
            base += min(10, len(structured.exit_rules) * 3)
            if structured.primary_timeframe:
                base += 5
            required_missing = sum(1 for m in missing if m.severity == "required")
            base -= required_missing * 10
            return max(0, min(100, base))

        if card is None:
            return 0
        corpus = " ".join(
            card.entry_conditions
            + card.confirmation_conditions
            + card.stop_loss
            + card.take_profit_plan
        ).lower()
        tokens = sum(
            1 for t in ("pullback", "ema", "rsi", "breakout", "stop", "tp1") if t in corpus
        )
        token_score = min(35, tokens * 6)
        field_score = 0
        if card.entry_conditions:
            field_score += 5
        if card.stop_loss:
            field_score += 5
        if card.take_profit_plan:
            field_score += 5
        if card.timeframes:
            field_score += 5
        if any(m.field_key == "rule_conditions_vague" for m in missing):
            token_score = min(token_score, 25)
        return min(69, token_score + field_score)

    def _band(self, score: int) -> TestabilityBand:
        if score >= 70:
            return TestabilityBand.MACHINE_TESTABLE
        if score >= 40:
            return TestabilityBand.PARTIAL
        return TestabilityBand.VAGUE

    def _analyze_rule_quality(
        self,
        structured: StructuredRules | None,
    ) -> tuple[list[str], list[str], list[str]]:
        if structured is None:
            return [], [], ["Add structured entry and exit rule blocks in Strategy Lab."]
        unsupported: list[str] = []
        ambiguous: list[str] = []
        suggested: list[str] = []
        for entry in structured.entry_rules:
            if not entry.conditions and entry.trigger_type.value in {
                "liquidity_sweep",
                "reclaim",
                "failed_breakout",
            }:
                ambiguous.append(f"Entry '{entry.trigger_type.value}' lacks lookback/conditions.")
                suggested.append(
                    f"Add timeframe and lookback to {entry.trigger_type.value} entry block."
                )
        for exit_rule in structured.exit_rules:
            if exit_rule.rule_type.value == "runner_structure_break" and not exit_rule.conditions:
                suggested.append("Define structure-break conditions for runner exit.")
            if exit_rule.rule_type.value in {"atr_stop", "swing_stop"} and exit_rule.value is None:
                ambiguous.append(f"Exit '{exit_rule.rule_type.value}' missing value/lookback.")
        if not structured.no_trade_rules:
            suggested.append("Add at least one no-trade filter (e.g. daily loss lock).")
        return unsupported, ambiguous, suggested
