"""Deterministic next-action priority for the trader-first dashboard."""

from __future__ import annotations

from app.schemas.dashboard import (
    AlertsLessonsSummary,
    DailyDisciplineSnapshot,
    NextRecommendedAction,
    StrategyReadinessSummary,
)
from app.schemas.market_watcher import MarketWatcherBridgeStatus, MarketWatcherStatus


def _plural_strategy(count: int) -> str:
    return "strategy" if count == 1 else "strategies"


def resolve_next_recommended_action(
    *,
    real_trading_enabled: bool,
    daily: DailyDisciplineSnapshot | None,
    alerts_lessons: AlertsLessonsSummary | None,
    strategy_readiness: StrategyReadinessSummary | None,
    market_watcher: MarketWatcherStatus | None,
    bridge: MarketWatcherBridgeStatus | None,
) -> NextRecommendedAction:
    if real_trading_enabled:
        return NextRecommendedAction(
            action="Review safety settings immediately.",
            reason="Real trading is not disabled — paper-only posture is compromised.",
            link="/settings",
            priority=1,
        )

    if daily is not None and daily.loss_lock_active:
        return NextRecommendedAction(
            action="Review only — daily loss protection is active.",
            reason="Paper PnL reached your configured daily loss limit.",
            link="/analytics",
            priority=2,
        )

    if daily is not None and daily.green_day_protection_active:
        return NextRecommendedAction(
            action="Consider pausing new entries and reviewing today's paper results.",
            reason="Green-day protection is active after reaching your daily target.",
            link="/analytics",
            priority=3,
        )

    critical_alerts = 0
    if alerts_lessons is not None:
        critical_alerts = sum(
            1 for alert in alerts_lessons.latest_high_priority if alert.severity.value == "critical"
        )
        if critical_alerts > 0 or alerts_lessons.unread_alerts > 0:
            unread = alerts_lessons.unread_alerts
            return NextRecommendedAction(
                action="Review new alerts (alerts never execute trades).",
                reason=(
                    f"{unread} unread alert{'s' if unread != 1 else ''} need attention."
                    if unread
                    else "Critical alerts need attention."
                ),
                link="/alerts",
                priority=4,
            )

    pending_lessons = alerts_lessons.pending_lessons if alerts_lessons else 0
    if pending_lessons > 0:
        return NextRecommendedAction(
            action="Review pending lesson candidates.",
            reason=(
                f"{pending_lessons} learning signal{'s' if pending_lessons != 1 else ''} "
                "await review before becoming rules."
            ),
            link="/lessons",
            priority=5,
        )

    counts = strategy_readiness.counts if strategy_readiness else None
    if counts and counts.needs_structure > 0:
        return NextRecommendedAction(
            action="Structure a strategy so it can be backtested.",
            reason=(
                f"{counts.needs_structure} {_plural_strategy(counts.needs_structure)} "
                "need structured rules."
            ),
            link="/strategy-lab",
            priority=6,
        )

    if counts and counts.ready_for_backtest > 0:
        return NextRecommendedAction(
            action="Run a backtest to gather a performance sample.",
            reason=(
                f"{counts.ready_for_backtest} {_plural_strategy(counts.ready_for_backtest)} "
                "are ready for backtest."
            ),
            link="/strategy-lab",
            priority=7,
        )

    if counts and counts.paper_eligible > 0:
        return NextRecommendedAction(
            action="Start or review paper validation for an eligible strategy.",
            reason=(
                f"{counts.paper_eligible} {_plural_strategy(counts.paper_eligible)} "
                "can enter paper validation."
            ),
            link="/strategy-lab",
            priority=8,
        )

    fresh_observations = 0
    if market_watcher is not None and market_watcher.last_scan_at is not None:
        fresh_observations = 1
    if bridge is not None and (bridge.scans_triggered_last_tick or 0) > 0:
        fresh_observations = max(fresh_observations, bridge.scans_triggered_last_tick)

    if fresh_observations > 0:
        return NextRecommendedAction(
            action="Review market watcher observations.",
            reason="Fresh market observations may inform your next paper validation scan.",
            link="/market-watcher",
            priority=9,
        )

    return NextRecommendedAction(
        action="No forced action — wait patiently for a high-quality setup.",
        reason="You're up to date on paper workflow, discipline, and review items.",
        link="/",
        priority=10,
    )
