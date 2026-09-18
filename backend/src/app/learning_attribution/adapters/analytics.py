"""Strategy/pattern and human-vs-system rollups over attribution records.

Does not query or mutate JournalStatisticsService internals. REJECT/SKIP are
funnel counts only and never enter executed-outcome rates.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.learning_attribution.contracts import AttributionRecord
from app.learning_attribution.memory import InMemoryAttributionStore
from app.learning_attribution.ports import AttributionStore
from app.market_contracts.models import CanonicalDecimal, CanonicalModel


class StrategyPatternRollup(CanonicalModel):
    strategy_version_id: UUID
    setup_definition_id: UUID
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
    executed_win_rate: CanonicalDecimal | None = None


class HumanVsSystemCohortRollup(CanonicalModel):
    human_reject_or_skip: int
    human_approvals: int
    paper_system_executions: int
    executed_outcomes: int
    setup_confirmed_count: int


class AttributionAnalyticsSnapshot(CanonicalModel):
    organization_id: UUID
    patterns: tuple[StrategyPatternRollup, ...] = Field(default_factory=tuple)
    human_vs_system: HumanVsSystemCohortRollup


def rollup_organization(
    store: AttributionStore,
    *,
    organization_id: UUID,
) -> AttributionAnalyticsSnapshot:
    records = store.list_for_organization(organization_id)
    grouped: dict[tuple[UUID, UUID], list[AttributionRecord]] = {}
    for record in records:
        key = (
            record.facts.strategy_pattern.strategy_version_id,
            record.facts.strategy_pattern.setup_definition_id,
        )
        grouped.setdefault(key, []).append(record)

    patterns: list[StrategyPatternRollup] = []
    for (strategy_version_id, setup_definition_id), group in sorted(
        grouped.items(), key=lambda item: (str(item[0][0]), str(item[0][1]))
    ):
        executed = [item for item in group if item.facts.outcome.eligible]
        wins = sum(1 for item in executed if item.facts.strategy_pattern.win)
        closed = sum(1 for item in group if item.facts.strategy_pattern.closed)
        win_rate = (Decimal(wins) / Decimal(len(executed))) if executed else None
        patterns.append(
            StrategyPatternRollup(
                strategy_version_id=strategy_version_id,
                setup_definition_id=setup_definition_id,
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
                executed_win_rate=win_rate,
            )
        )

    human_vs = HumanVsSystemCohortRollup(
        human_reject_or_skip=sum(
            1
            for item in records
            if item.facts.strategy_pattern.rejected or item.facts.strategy_pattern.skipped
        ),
        human_approvals=sum(1 for item in records if item.facts.strategy_pattern.plan_approved),
        paper_system_executions=sum(1 for item in records if item.facts.strategy_pattern.filled),
        executed_outcomes=sum(1 for item in records if item.facts.outcome.eligible),
        setup_confirmed_count=sum(1 for item in records if item.facts.setup_quality.confirmed),
    )
    return AttributionAnalyticsSnapshot(
        organization_id=organization_id,
        patterns=tuple(patterns),
        human_vs_system=human_vs,
    )


def empty_store() -> InMemoryAttributionStore:
    return InMemoryAttributionStore()
