"""Lesson suggestions from attribution facts. Never auto-persists candidates."""

from __future__ import annotations

from app.learning_attribution.contracts import (
    AttributionRecord,
    ExecutionQuality,
    LessonSuggestionFact,
    RiskAdherence,
    TraderBehavior,
)
from app.schemas.human_vs_system import LessonCandidateSuggestion


def lesson_suggestions(record: AttributionRecord) -> tuple[LessonSuggestionFact, ...]:
    """Map quality axes to review suggestions. persist is always false."""
    facts = record.facts
    suggestions: list[LessonSuggestionFact] = []
    behavior = facts.trader_behavior.axis
    if behavior is TraderBehavior.REJECTED:
        suggestions.append(
            LessonSuggestionFact(
                category="lifecycle_attribution",
                summary="Candidate was rejected. Recorded as trader behavior, not a trade result.",
                mistake_type="rejected_setup",
                severity="low",
                executed_trade_outcome=False,
            )
        )
    if behavior is TraderBehavior.SKIPPED:
        suggestions.append(
            LessonSuggestionFact(
                category="lifecycle_attribution",
                summary="Candidate was skipped. Recorded as trader behavior, not a trade result.",
                mistake_type="skipped_setup",
                severity="low",
                executed_trade_outcome=False,
            )
        )
    if facts.execution_quality.axis is ExecutionQuality.EARLY_EXIT and facts.outcome.eligible:
        suggestions.append(
            LessonSuggestionFact(
                category="lifecycle_attribution",
                summary="Closed trade captured under 50% of available profit.",
                mistake_type="early_exit",
                severity="medium",
                executed_trade_outcome=True,
            )
        )
    if (
        facts.execution_quality.axis is ExecutionQuality.SLIPPAGE_DEVIATION
        and facts.outcome.eligible
    ):
        suggestions.append(
            LessonSuggestionFact(
                category="lifecycle_attribution",
                summary="Fill price deviated from the planned entry beyond 10 bps.",
                mistake_type="entry_slippage",
                severity="medium",
                executed_trade_outcome=True,
            )
        )
    if facts.risk_adherence.axis is RiskAdherence.STOP_VIOLATION and facts.outcome.eligible:
        suggestions.append(
            LessonSuggestionFact(
                category="lifecycle_attribution",
                summary="Exit price violated the planned stop beyond 10 bps.",
                mistake_type="stop_violation",
                severity="high",
                executed_trade_outcome=True,
            )
        )
    if facts.risk_adherence.axis is RiskAdherence.SIZE_OR_RISK_VIOLATION and facts.outcome.eligible:
        suggestions.append(
            LessonSuggestionFact(
                category="lifecycle_attribution",
                summary="Filled size deviated from the planned size beyond 100 bps.",
                mistake_type="size_or_risk_violation",
                severity="medium",
                executed_trade_outcome=True,
            )
        )
    return tuple(suggestions)


def as_human_vs_system_suggestions(
    record: AttributionRecord,
) -> list[LessonCandidateSuggestion]:
    """Existing lesson UI shape. Callers must still POST to persist."""
    return [
        LessonCandidateSuggestion(
            category=item.category,
            summary=item.summary,
            source_type="journal",
            severity=item.severity,
        )
        for item in lesson_suggestions(record)
    ]
