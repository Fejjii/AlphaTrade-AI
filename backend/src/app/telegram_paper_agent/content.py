"""Deterministic Telegram outbox text. No profitability claims. No LLM setup truth."""

from __future__ import annotations

from app.telegram_paper_agent.contracts import (
    MAX_TEXT_BYTES,
    JournalOutcomeView,
    LearningSummaryView,
    PaperNotificationKind,
    PaperTradeStatusView,
    WatcherScanNotice,
)

_PROFIT_CLAIMS = ("guaranteed", "will win", "autonomous profit")


def format_watcher_blocked_text(notice: WatcherScanNotice) -> str:
    text = (
        "Watcher paper alert (not a trade).\n"
        f"symbol: {notice.symbol}\n"
        f"status: {notice.status}\n"
        f"reason: {notice.reason_code}\n"
        "Evidence failed closed. No Candidate was minted. "
        "Telegram cannot override SetupAssessment or risk."
    )
    return guard_paper_text(text)


def format_confirmed_setup_footer(*, candidate_id: str) -> str:
    text = (
        "Paper Watcher minted a canonical Candidate on CONFIRMED_SETUP.\n"
        f"candidate_id: {candidate_id}\n"
        "Reply to discuss evidence, strategy, Candidate, or risk. "
        "Mutating paper actions require an explicit identity-bound confirmation. "
        "Telegram cannot execute, approve a strategy, or enable live trading."
    )
    return guard_paper_text(text)


def format_journal_outcome_text(view: JournalOutcomeView) -> str:
    pnl = "n/a" if view.net_pnl is None else view.net_pnl
    text = (
        "Paper journal outcome (facts only, not a live fill).\n"
        f"trade_id: {view.trade_id}\n"
        f"symbol: {view.symbol}\n"
        f"status: {view.status}\n"
        f"result: {view.result or 'n/a'}\n"
        f"net_pnl: {pnl}\n"
        f"{view.summary}"
    )
    return guard_paper_text(text)


def format_paper_status_text(view: PaperTradeStatusView) -> str:
    text = (
        "Paper trade status (read-only).\n"
        f"execution_mode: {view.execution_mode}\n"
        f"real_trading_enabled: {view.real_trading_enabled}\n"
        f"open_positions: {view.open_positions}\n"
        f"open_orders: {view.open_orders}\n"
        f"{view.summary}"
    )
    return guard_paper_text(text)


def format_learning_summary_text(view: LearningSummaryView) -> str:
    facts = "\n".join(view.fact_lines) if view.fact_lines else "No learning facts bound."
    text = (
        f"{view.banner}\n"
        "Learning summary (explanation of recorded facts).\n"
        f"setup_quality: {view.setup_quality or 'n/a'}\n"
        f"execution_quality: {view.execution_quality or 'n/a'}\n"
        f"trader_behavior: {view.trader_behavior or 'n/a'}\n"
        f"{facts}"
    )
    return guard_paper_text(text)


def notification_kind_label(kind: PaperNotificationKind) -> str:
    return kind.value


def guard_paper_text(text: str) -> str:
    lowered = text.lower()
    for claim in _PROFIT_CLAIMS:
        if claim in lowered:
            raise ValueError("Paper Telegram text must not claim guaranteed returns.")
    if len(text) > MAX_TEXT_BYTES:
        raise ValueError("Paper Telegram text exceeds outbox bounds.")
    return text
