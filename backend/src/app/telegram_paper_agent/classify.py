"""Deterministic inbound intent classification. LLM wording is never authority."""

from __future__ import annotations

import re

from app.telegram_paper_agent.contracts import DiscussionIntent

_CONFIRM = re.compile(r"^\s*i\s+confirm\b", re.IGNORECASE)

_RULES: tuple[tuple[DiscussionIntent, tuple[str, ...]], ...] = (
    (
        DiscussionIntent.REQUEST_ENABLE_LIVE,
        ("enable live", "live trading", "real trading", "mode d"),
    ),
    (
        DiscussionIntent.REQUEST_EXECUTE,
        (
            "execute paper",
            "place order",
            "place live",
            "send order",
            "buy now",
            "sell now",
            "execute_paper",
        ),
    ),
    (
        DiscussionIntent.REQUEST_MINT_CANDIDATE,
        ("mint candidate", "create candidate", "new candidate"),
    ),
    (
        DiscussionIntent.REQUEST_OVERRIDE_ASSESSMENT,
        (
            "override assessment",
            "mark confirmed",
            "force confirmed_setup",
            "ignore invalidat",
        ),
    ),
    (
        DiscussionIntent.REQUEST_OVERRIDE_RISK,
        ("override risk", "ignore the block", "ignore risk", "bypass risk"),
    ),
    (
        DiscussionIntent.REQUEST_APPROVE_STRATEGY,
        (
            "approve strategy",
            "approve this strategy",
            "approve the strategy",
            "activate strategy",
            "compile and approve",
        ),
    ),
    (DiscussionIntent.REQUEST_REJECT, ("reject candidate", "reject this")),
    (DiscussionIntent.REQUEST_SKIP, ("skip candidate", "skip this")),
    (DiscussionIntent.REQUEST_APPROVE, ("approve candidate", "approve this candidate")),
    (DiscussionIntent.EXPLAIN_EVIDENCE, ("evidence", "freshness", "window hash")),
    (DiscussionIntent.EXPLAIN_CANDIDATE, ("candidate", "setup assessment")),
    (DiscussionIntent.EXPLAIN_RISK, ("risk", "eligibility", "kill switch")),
    (DiscussionIntent.EXPLAIN_STRATEGY, ("strategy version", "compiled setup")),
    (DiscussionIntent.MARKET_CONTEXT, ("market context", "price", "cvd", "what is the market")),
    (DiscussionIntent.PAPER_TRADE_STATUS, ("paper status", "open position", "paper trade")),
    (DiscussionIntent.JOURNAL_OUTCOME, ("journal", "outcome", "closed trade")),
    (DiscussionIntent.LEARNING_SUMMARY, ("learning", "attribution", "lesson")),
    (DiscussionIntent.STRATEGY_DISCUSSION, ("strategy", "pattern", "setup idea")),
)


def classify_inbound_text(text: str) -> DiscussionIntent:
    stripped = text.strip()
    if not stripped:
        return DiscussionIntent.UNKNOWN
    if _CONFIRM.search(stripped):
        return DiscussionIntent.CONFIRM_MUTATION
    lowered = stripped.lower()
    for intent, needles in _RULES:
        if any(needle in lowered for needle in needles):
            return intent
    return DiscussionIntent.UNKNOWN


def is_explicit_confirm(text: str) -> bool:
    return _CONFIRM.search(text.strip()) is not None
