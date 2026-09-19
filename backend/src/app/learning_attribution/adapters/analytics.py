"""Strategy/pattern and human-vs-system rollups over attribution records.

Does not query or mutate JournalStatisticsService internals. REJECT/SKIP are
funnel counts only and never enter executed-outcome rates. Paper and demo
venue cohorts are aggregated separately.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.learning_attribution.contracts import (
    AttributionRecord,
    LearningVenueMode,
    RiskAdherence,
)
from app.learning_attribution.memory import InMemoryAttributionStore
from app.learning_attribution.ports import AttributionStore
from app.market_contracts.models import CanonicalDecimal, CanonicalModel


class StrategyPatternRollup(CanonicalModel):
    strategy_version_id: UUID
    setup_definition_id: UUID
    learning_venue_mode: LearningVenueMode
    sample_candidates: int
    rejected_count: int
    skipped_count: int
    plan_approved_count: int
    filled_count: int
    closed_count: int
    executed_outcome_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    risk_adhered_count: int
    risk_stop_violation_count: int
    executed_win_rate: CanonicalDecimal | None = None


class HumanVsSystemCohortRollup(CanonicalModel):
    learning_venue_mode: LearningVenueMode | None = None
    human_reject_or_skip: int
    human_approvals: int
    paper_system_executions: int
    executed_outcomes: int
    setup_confirmed_count: int
    risk_adhered_count: int
    risk_stop_violation_count: int
    human_approved_executed_wins: int
    human_approved_executed_losses: int


class AttributionAnalyticsSnapshot(CanonicalModel):
    organization_id: UUID
    learning_venue_mode: LearningVenueMode | None = None
    patterns: tuple[StrategyPatternRollup, ...] = Field(default_factory=tuple)
    human_vs_system: HumanVsSystemCohortRollup


def rollup_organization(
    store: AttributionStore,
    *,
    organization_id: UUID,
    learning_venue_mode: LearningVenueMode | None = None,
) -> AttributionAnalyticsSnapshot:
    records = _scoped_records(
        store, organization_id=organization_id, learning_venue_mode=learning_venue_mode
    )
    grouped: dict[tuple[UUID, UUID, LearningVenueMode], list[AttributionRecord]] = {}
    for record in records:
        pattern = record.facts.strategy_pattern
        key = (
            pattern.strategy_version_id,
            pattern.setup_definition_id,
            record.facts.learning_venue_mode,
        )
        grouped.setdefault(key, []).append(record)

    patterns: list[StrategyPatternRollup] = []
    for (strategy_version_id, setup_definition_id, venue_mode), group in sorted(
        grouped.items(),
        key=lambda item: (str(item[0][0]), str(item[0][1]), item[0][2].value),
    ):
        executed = [item for item in group if item.facts.outcome.eligible]
        wins = sum(1 for item in executed if item.facts.strategy_pattern.win)
        closed = sum(1 for item in group if item.facts.strategy_pattern.closed)
        win_rate = (Decimal(wins) / Decimal(len(executed))) if executed else None
        patterns.append(
            StrategyPatternRollup(
                strategy_version_id=strategy_version_id,
                setup_definition_id=setup_definition_id,
                learning_venue_mode=venue_mode,
                sample_candidates=len(group),
                rejected_count=sum(1 for item in group if item.facts.strategy_pattern.rejected),
                skipped_count=sum(1 for item in group if item.facts.strategy_pattern.skipped),
                plan_approved_count=sum(
                    1 for item in group if item.facts.strategy_pattern.plan_approved
                ),
                filled_count=sum(1 for item in group if item.facts.strategy_pattern.filled),
                closed_count=closed,
                executed_outcome_count=len(executed),
                win_count=wins,
                loss_count=sum(1 for item in executed if item.facts.strategy_pattern.loss),
                breakeven_count=sum(
                    1 for item in executed if item.facts.strategy_pattern.breakeven
                ),
                risk_adhered_count=sum(
                    1 for item in group if item.facts.risk_adherence.axis is RiskAdherence.ADHERED
                ),
                risk_stop_violation_count=sum(
                    1
                    for item in group
                    if item.facts.risk_adherence.axis is RiskAdherence.STOP_VIOLATION
                ),
                executed_win_rate=win_rate,
            )
        )

    approved_executed = [
        item
        for item in records
        if item.facts.strategy_pattern.plan_approved and item.facts.outcome.eligible
    ]
    human_vs = HumanVsSystemCohortRollup(
        learning_venue_mode=learning_venue_mode,
        human_reject_or_skip=sum(
            1
            for item in records
            if item.facts.strategy_pattern.rejected or item.facts.strategy_pattern.skipped
        ),
        human_approvals=sum(1 for item in records if item.facts.strategy_pattern.plan_approved),
        paper_system_executions=sum(1 for item in records if item.facts.strategy_pattern.filled),
        executed_outcomes=sum(1 for item in records if item.facts.outcome.eligible),
        setup_confirmed_count=sum(1 for item in records if item.facts.setup_quality.confirmed),
        risk_adhered_count=sum(
            1 for item in records if item.facts.risk_adherence.axis is RiskAdherence.ADHERED
        ),
        risk_stop_violation_count=sum(
            1 for item in records if item.facts.risk_adherence.axis is RiskAdherence.STOP_VIOLATION
        ),
        human_approved_executed_wins=sum(
            1 for item in approved_executed if item.facts.strategy_pattern.win
        ),
        human_approved_executed_losses=sum(
            1 for item in approved_executed if item.facts.strategy_pattern.loss
        ),
    )
    return AttributionAnalyticsSnapshot(
        organization_id=organization_id,
        learning_venue_mode=learning_venue_mode,
        patterns=tuple(patterns),
        human_vs_system=human_vs,
    )


def _scoped_records(
    store: AttributionStore,
    *,
    organization_id: UUID,
    learning_venue_mode: LearningVenueMode | None,
) -> tuple[AttributionRecord, ...]:
    records = store.list_for_organization(organization_id)
    if learning_venue_mode is None:
        return records
    return tuple(
        record for record in records if record.facts.learning_venue_mode is learning_venue_mode
    )


def empty_store() -> InMemoryAttributionStore:
    return InMemoryAttributionStore()
