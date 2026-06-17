"""Detect strategy workflow questions for agent routing (Slice 34-35)."""

from __future__ import annotations

from app.schemas.agent import Intent


def classify_strategy_workflow(message: str) -> Intent | None:
    """Return a strategy-workflow intent when the message matches known patterns."""
    lowered = message.lower()

    if "compare" in lowered and ("trade" in lowered or "system" in lowered):
        return Intent.HUMAN_VS_SYSTEM
    if "exit too early" in lowered or "did i exit too early" in lowered:
        return Intent.EARLY_EXIT_QUERY
    if "respect my stop" in lowered or "did i respect my stop" in lowered:
        return Intent.STOP_DISCIPLINE_QUERY
    if "system would have done" in lowered or "what would the system have done" in lowered:
        return Intent.HUMAN_VS_SYSTEM
    if "testable" in lowered and "strateg" in lowered:
        return Intent.STRATEGY_TESTABILITY
    if "more structured" in lowered or "structured rule" in lowered:
        return Intent.STRUCTURE_STRATEGY
    if "rule is missing" in lowered and "backtest" in lowered:
        return Intent.STRATEGY_TESTABILITY
    if "convert" in lowered and ("plain english" in lowered or "structured" in lowered):
        return Intent.STRUCTURE_STRATEGY
    if "not following the plan" in lowered or "lose by not following" in lowered:
        return Intent.HUMAN_VS_SYSTEM
    if "manual level" in lowered or ("level" in lowered and "coin" in lowered):
        return Intent.MANUAL_LEVELS
    if "loss acceptable" in lowered or "loss acceptance" in lowered:
        return Intent.LOSS_ACCEPTANCE
    if "invalidation" in lowered or ("stop loss" in lowered and "?" in message):
        return Intent.INVALIDATION_QUERY
    if "position size" in lowered or "calculate size" in lowered or "sizing" in lowered:
        return Intent.POSITION_SIZE
    if "paper eligible" in lowered or "paper eligibility" in lowered:
        return Intent.BACKTEST_ELIGIBILITY
    if "blocked from paper" in lowered or "paper validation block" in lowered:
        return Intent.PAPER_ELIGIBILITY_BLOCKERS
    if "which lessons" in lowered and "update" in lowered and "strateg" in lowered:
        return Intent.LESSON_STRATEGY_UPDATE
    if "create" in lowered and "strategy version" in lowered and "lesson" in lowered:
        return Intent.LESSON_CREATE_VERSION
    if "accepted lessons" in lowered and "linked" in lowered:
        return Intent.LESSON_STRATEGY_LINKED
    if "unresolved mistake" in lowered or (
        "blocking" in lowered and "strateg" in lowered and "lesson" in lowered
    ):
        return Intent.LESSON_UNRESOLVED_BLOCKERS
    if "fix before backtest" in lowered or (
        "before backtest" in lowered and ("fix" in lowered or "what should" in lowered)
    ):
        return Intent.BACKTEST_PREP
    if "backtest" in lowered and (
        "show" in lowered or "result" in lowered or "what did" in lowered
    ):
        return Intent.BACKTEST_RESULTS
    if "backtest" in lowered and ("why" in lowered and "not validated" in lowered):
        return Intent.BACKTEST_RESULTS
    if "backtest" in lowered and any(
        token in lowered
        for token in ("btc", "eth", "sol", "15m", "1h", "4h", "run", "this strategy")
    ):
        return Intent.BACKTEST_RUN
    if "backtest" in lowered and ("next" in lowered or "needs" in lowered or "sample" in lowered):
        return Intent.BACKTEST_QUEUE
    if "validated" in lowered and "strateg" in lowered:
        return Intent.STRATEGY_STATUS
    if "strategy card" in lowered or (
        "build" in lowered and "strateg" in lowered and "idea" in lowered
    ):
        return Intent.STRATEGY_CARD
    if "analyze" in lowered and "strateg" in lowered:
        return Intent.PRE_TRADE
    if "pre-trade" in lowered or "pre trade" in lowered:
        return Intent.PRE_TRADE
    if "pending review" in lowered and "lesson" in lowered:
        return Intent.LESSON_PENDING_QUERY
    if "accepted lesson" in lowered or ("my lessons" in lowered and "accepted" in lowered):
        return Intent.LESSON_ACCEPTED_QUERY
    if "accept" in lowered and "lesson" in lowered:
        from app.agents.mutation_policy import is_question_message

        if is_question_message(message):
            return Intent.LESSON_RULE_SUGGEST
        return Intent.LESSON_ACCEPT
    if "reject" in lowered and "lesson" in lowered:
        from app.agents.mutation_policy import is_question_message

        if is_question_message(message):
            return Intent.LESSON_RULE_SUGGEST
        return Intent.LESSON_REJECT
    if "rule should i update" in lowered or "update from this mistake" in lowered:
        return Intent.LESSON_RULE_SUGGEST
    if "runner rule" in lowered and "strateg" in lowered:
        return Intent.ADD_RUNNER_RULE
    if "early exit" in lowered and "lesson" in lowered:
        return Intent.LESSON_ACCEPTED_QUERY
    if "stop loss refusal" in lowered or ("stop" in lowered and "refusal" in lowered):
        return Intent.LESSON_ACCEPTED_QUERY
    if "start paper validation" in lowered or (
        "paper validation" in lowered and "start" in lowered
    ):
        return Intent.PAPER_VALIDATION_START
    if "scan" in lowered and ("strateg" in lowered or "paper" in lowered):
        return Intent.PAPER_VALIDATION_SCAN
    if "paper signal" in lowered or "what paper signals" in lowered:
        return Intent.PAPER_VALIDATION_QUERY
    if "paper trades are open" in lowered or "open paper" in lowered:
        return Intent.PAPER_VALIDATION_QUERY
    if "what did the paper bot" in lowered or "paper bot do" in lowered:
        return Intent.PAPER_VALIDATION_QUERY
    if "paper validated" in lowered and "strateg" in lowered:
        return Intent.PAPER_VALIDATION_QUERY
    if "paper validation metric" in lowered or "show paper validation" in lowered:
        return Intent.PAPER_VALIDATION_QUERY
    if "still restricted" in lowered and "strateg" in lowered:
        return Intent.PAPER_VALIDATION_QUERY
    if "improve or retire" in lowered and "strateg" in lowered:
        return Intent.PAPER_VALIDATION_RECOMMEND
    if (
        "paper scheduler" in lowered
        or "scheduler running" in lowered
        or "scheduler tick" in lowered
    ):
        return Intent.PAPER_SCHEDULER_QUERY
    if "what alerts" in lowered or "my alerts" in lowered or "unread alert" in lowered:
        return Intent.PAPER_ALERTS_QUERY
    if (
        "external alert" in lowered
        or "alert delivery" in lowered
        or "deliver pending alert" in lowered
        or "why was this alert not delivered" in lowered
        or "why was alert not delivered" in lowered
    ):
        return Intent.ALERT_DELIVERY_QUERY
    if (
        "market watcher" in lowered
        or "symbols are being watched" in lowered
        or "symbols being watched" in lowered
        or "setup signal appear" in lowered
        or "did any setup signal" in lowered
    ):
        return Intent.MARKET_WATCHER_QUERY
    if "market data fresh" in lowered or "is the market data fresh" in lowered:
        return Intent.MARKET_WATCHER_QUERY
    if "why was" in lowered and "skipped" in lowered:
        return Intent.PAPER_VALIDATION_QUERY
    if "data stale" in lowered or "is the data stale" in lowered:
        return Intent.PAPER_VALIDATION_QUERY
    if "blockers" in lowered and "paper" in lowered:
        return Intent.PAPER_VALIDATION_QUERY
    if "last paper validation run" in lowered or "what happened in the last paper" in lowered:
        return Intent.PAPER_VALIDATION_QUERY

    return None


def is_strategy_workflow_intent(intent: Intent) -> bool:
    return intent in {
        Intent.STRATEGY_CARD,
        Intent.PRE_TRADE,
        Intent.POSITION_SIZE,
        Intent.INVALIDATION_QUERY,
        Intent.LOSS_ACCEPTANCE,
        Intent.HUMAN_VS_SYSTEM,
        Intent.MANUAL_LEVELS,
        Intent.STRATEGY_STATUS,
        Intent.BACKTEST_QUEUE,
        Intent.BACKTEST_RUN,
        Intent.BACKTEST_RESULTS,
        Intent.BACKTEST_ELIGIBILITY,
        Intent.EARLY_EXIT_QUERY,
        Intent.STOP_DISCIPLINE_QUERY,
        Intent.STRATEGY_TESTABILITY,
        Intent.STRUCTURE_STRATEGY,
        Intent.LESSON_PENDING_QUERY,
        Intent.LESSON_ACCEPTED_QUERY,
        Intent.LESSON_ACCEPT,
        Intent.LESSON_REJECT,
        Intent.LESSON_RULE_SUGGEST,
        Intent.ADD_RUNNER_RULE,
        Intent.PAPER_ELIGIBILITY_BLOCKERS,
        Intent.LESSON_STRATEGY_UPDATE,
        Intent.LESSON_CREATE_VERSION,
        Intent.LESSON_STRATEGY_LINKED,
        Intent.LESSON_UNRESOLVED_BLOCKERS,
        Intent.BACKTEST_PREP,
        Intent.PAPER_VALIDATION_START,
        Intent.PAPER_VALIDATION_SCAN,
        Intent.PAPER_VALIDATION_QUERY,
        Intent.PAPER_VALIDATION_RECOMMEND,
        Intent.PAPER_SCHEDULER_QUERY,
        Intent.PAPER_ALERTS_QUERY,
        Intent.ALERT_DELIVERY_QUERY,
        Intent.MARKET_WATCHER_QUERY,
    }
