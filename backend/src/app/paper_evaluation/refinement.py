"""Deterministic refinement suggestions. Never compiles or activates a strategy."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid5

from app.paper_evaluation.contracts import (
    NARRATIVE_NOT_FACT_BANNER,
    PaperEvaluationFacts,
    RefinementSuggestion,
)
from app.paper_evaluation.errors import RefinementActivationForbiddenError
from app.schemas.journal_statistics import SampleConfidence

_REFINEMENT_NAMESPACE = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
_HIGH_FALSE_SIGNAL = Decimal("0.6000")
_HIGH_BLOCK = Decimal("0.5000")
_HIGH_MISS = Decimal("0.5000")
_HIGH_STALE = Decimal("0.3000")
_LOW_CAPTURE = Decimal("50.00")


def refinement_suggestions(
    facts: PaperEvaluationFacts,
    *,
    narrative: str | None = None,
) -> tuple[RefinementSuggestion, ...]:
    """Map measurement facts to review suggestions. activate is always false."""

    if narrative is not None and not narrative.startswith(NARRATIVE_NOT_FACT_BANNER[:18]):
        labeled = f"{NARRATIVE_NOT_FACT_BANNER}\n{narrative}"
    else:
        labeled = narrative
    suggestions: list[RefinementSuggestion] = []
    false_rate = facts.false_signals.false_signal_rate
    if (
        false_rate is not None
        and false_rate >= _HIGH_FALSE_SIGNAL
        and facts.false_signals.executed_outcomes >= 5
    ):
        suggestions.append(
            _suggestion(
                facts,
                category="false_signal",
                summary=(
                    "Confirmed setups that reached a closed paper outcome lost often enough "
                    "to review trigger tightness. Suggestion only."
                ),
                severity="high",
                narrative=labeled,
            )
        )
    if facts.blocked.blocked_count and facts.conversion.candidates:
        block_rate = Decimal(facts.blocked.blocked_count) / Decimal(facts.conversion.candidates)
        if block_rate >= _HIGH_BLOCK:
            top = facts.blocked.by_reason[0][0] if facts.blocked.by_reason else "blocked"
            suggestions.append(
                _suggestion(
                    facts,
                    category="blocked_trade",
                    summary=(
                        f"Many confirmed Candidates were ActionEligibility BLOCKED "
                        f"(top reason {top}). Review risk/account gates, not setup truth."
                    ),
                    severity="medium",
                    narrative=labeled,
                )
            )
    misses = (
        facts.missed_opportunities.rejected_confirmed
        + facts.missed_opportunities.skipped_confirmed
        + facts.missed_opportunities.eligible_not_approved
    )
    if facts.conversion.confirmed_setups and misses:
        miss_rate = Decimal(misses) / Decimal(facts.conversion.confirmed_setups)
        if miss_rate >= _HIGH_MISS:
            suggestions.append(
                _suggestion(
                    facts,
                    category="missed_opportunity",
                    summary=(
                        "Confirmed setups were often rejected, skipped, or left unapproved. "
                        "Funnel miss only — no counterfactual PnL."
                    ),
                    severity="medium",
                    narrative=labeled,
                )
            )
    capture = facts.strategy_overall.average_capture_pct
    if (
        capture is not None
        and capture < _LOW_CAPTURE
        and facts.strategy_overall.capture_sample_count
    ):
        suggestions.append(
            _suggestion(
                facts,
                category="execution_capture",
                summary="Closed paper trades captured under 50% of recorded available profit.",
                severity="medium",
                narrative=labeled,
            )
        )
    if facts.rule_adherence.stop_violation_count or facts.rule_adherence.journal_violated_count:
        suggestions.append(
            _suggestion(
                facts,
                category="rule_adherence",
                summary=(
                    "Recorded stop or journal rule violations. Review plan adherence, not setup "
                    "truth."
                ),
                severity="high",
                narrative=labeled,
            )
        )
    stale_rate = facts.data_quality.stale_or_unavailable_rate
    if stale_rate is not None and stale_rate >= _HIGH_STALE:
        suggestions.append(
            _suggestion(
                facts,
                category="data_quality",
                summary=(
                    "Stale or unavailable evidence is common. Conservative fail-closed behavior "
                    "is required."
                ),
                severity="high",
                narrative=labeled,
            )
        )
    if len(facts.strategy_versions) >= 2:
        ranked = [
            item
            for item in facts.strategy_versions
            if item.expectancy is not None and item.confidence is not SampleConfidence.INSUFFICIENT
        ]
        if len(ranked) >= 2:
            best = max(ranked, key=lambda item: item.expectancy or Decimal("0"))
            worst = min(ranked, key=lambda item: item.expectancy or Decimal("0"))
            if best.strategy_version_id != worst.strategy_version_id:
                suggestions.append(
                    _suggestion(
                        facts,
                        category="strategy_version_comparison",
                        summary=(
                            "One compiled strategy version has weaker paper expectancy than "
                            "another. Compare versions; do not auto-promote."
                        ),
                        severity="low",
                        strategy_version_id=worst.strategy_version_id,
                        narrative=labeled,
                    )
                )
    return tuple(suggestions)


def refuse_activation(suggestion: RefinementSuggestion) -> None:
    """Any activation attempt fails closed. Suggestions are never executable."""

    raise RefinementActivationForbiddenError(
        details={
            "suggestion_id": str(suggestion.suggestion_id),
            "activate": suggestion.activate,
            "auto_activate": suggestion.auto_activate,
        }
    )


def _suggestion(
    facts: PaperEvaluationFacts,
    *,
    category: str,
    summary: str,
    severity: str,
    strategy_version_id: UUID | None = None,
    narrative: str | None,
) -> RefinementSuggestion:
    suggestion_id = uuid5(
        _REFINEMENT_NAMESPACE,
        f"{facts.organization_id}:{facts.content_hash}:{category}",
    )
    return RefinementSuggestion(
        suggestion_id=suggestion_id,
        organization_id=facts.organization_id,
        category=category,
        summary=summary,
        strategy_version_id=strategy_version_id,
        evidence_facts_hash=facts.content_hash,
        severity=severity,
        narrative_explanation=narrative,
    )
