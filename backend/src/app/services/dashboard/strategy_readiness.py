"""Deterministic strategy readiness grouping (mirrors frontend strategy-status.ts)."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.dashboard import (
    StrategyActionItem,
    StrategyReadinessCounts,
    StrategyReadinessSummary,
)
from app.schemas.strategy_library import UserStrategy

_COMPLETED_BACKTEST = frozenset({"completed", "complete", "passed", "succeeded"})
_RUNNING_PAPER = frozenset({"running", "active", "in_progress"})


@dataclass(frozen=True)
class StrategyStatusView:
    label: str
    bucket: str
    next_action: str
    blockers: tuple[str, ...] = ()


def strategy_status_view(strategy: UserStrategy) -> StrategyStatusView:
    validation = (
        strategy.validation_status.value if strategy.validation_status else "draft"
    ).lower()
    backtest = (strategy.backtest_status.value if strategy.backtest_status else "not_run").lower()
    paper = (
        strategy.paper_validation_status.value
        if strategy.paper_validation_status
        else "not_started"
    ).lower()

    if paper in {"restricted", "blocked"}:
        return StrategyStatusView(
            "Restricted",
            "restricted",
            "Review blockers before retrying paper validation.",
            ("Paper validation restricted",),
        )
    if paper in {"validated", "complete", "completed"}:
        return StrategyStatusView(
            "Paper validated",
            "paper_validated",
            "Review results and fold lessons into the next version.",
        )
    if paper in _RUNNING_PAPER:
        return StrategyStatusView(
            "Paper validation running",
            "paper_validation_running",
            "Review latest scans and simulated trades.",
        )
    if strategy.paper_eligible:
        return StrategyStatusView(
            "Paper eligible",
            "paper_eligible",
            "Start paper validation to simulate this strategy.",
        )
    if backtest in _COMPLETED_BACKTEST:
        return StrategyStatusView(
            "Needs more sample",
            "needs_more_sample",
            "Gather a larger backtest sample to unlock paper validation.",
        )
    if backtest == "running":
        return StrategyStatusView(
            "Backtest running",
            "ready_for_backtest",
            "Backtest in progress — check back shortly.",
        )
    if validation in {"draft", "needs_structure"}:
        return StrategyStatusView(
            "Needs structure",
            "needs_structure",
            "Add structured rules so the strategy can be backtested.",
        )
    return StrategyStatusView(
        "Ready for backtest",
        "ready_for_backtest",
        "Run a backtest to gather a performance sample.",
    )


_PRIORITY = (
    "restricted",
    "needs_structure",
    "ready_for_backtest",
    "needs_more_sample",
    "paper_eligible",
    "paper_validation_running",
    "paper_validated",
)


def build_strategy_readiness(strategies: list[UserStrategy]) -> StrategyReadinessSummary:
    counts = StrategyReadinessCounts()
    items: list[tuple[int, StrategyActionItem]] = []

    for strategy in strategies:
        view = strategy_status_view(strategy)
        current = getattr(counts, view.bucket)
        setattr(counts, view.bucket, current + 1)
        priority = _PRIORITY.index(view.bucket) if view.bucket in _PRIORITY else len(_PRIORITY)
        items.append(
            (
                priority,
                StrategyActionItem(
                    strategy_id=strategy.id,
                    name=strategy.name,
                    status=view.label,
                    next_action=view.next_action,
                    blockers=list(view.blockers),
                    link_hint=f"/strategy-lab/{strategy.id}",
                ),
            )
        )

    items.sort(key=lambda pair: pair[0])
    return StrategyReadinessSummary(
        counts=counts,
        top_needing_action=[item for _, item in items[:5]],
    )
