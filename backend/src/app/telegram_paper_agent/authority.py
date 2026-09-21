"""Refusals for authorities Telegram must never hold."""

from __future__ import annotations

from app.telegram_paper_agent.contracts import DiscussionIntent

_REFUSALS: dict[DiscussionIntent, str] = {
    DiscussionIntent.REQUEST_EXECUTE: (
        "Telegram cannot place an order. EXECUTE_PAPER_PLAN is not a Telegram action."
    ),
    DiscussionIntent.REQUEST_APPROVE_STRATEGY: (
        "Telegram cannot approve or activate a strategy. Strategy approval is a "
        "separate explicit path and is never implicit in a chat message."
    ),
    DiscussionIntent.REQUEST_OVERRIDE_ASSESSMENT: (
        "Telegram cannot override SetupAssessment. Setup truth stays on the evaluator."
    ),
    DiscussionIntent.REQUEST_OVERRIDE_RISK: (
        "Telegram cannot override risk. RiskEngine BLOCK remains final."
    ),
    DiscussionIntent.REQUEST_MINT_CANDIDATE: (
        "Telegram cannot mint a Candidate. Candidates persist only from CONFIRMED_SETUP."
    ),
    DiscussionIntent.REQUEST_ENABLE_LIVE: (
        "Telegram cannot enable live trading. Real execution stays disabled."
    ),
}


def refusal_for(intent: DiscussionIntent) -> str | None:
    return _REFUSALS.get(intent)
