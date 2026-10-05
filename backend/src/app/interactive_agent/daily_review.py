"""Bounded Daily Review reads. No narrative model, market lookup or domain write."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.errors import ValidationAppError
from app.daily_review.contracts import DailyReview, ReviewItem, ReviewTopic
from app.daily_review.reader import DailyReviewService
from app.daily_review.service import daily_window
from app.interactive_agent.actions import ActionRequest, DailyReviewInput


def route_daily_review(message: str) -> ActionRequest | None:
    """Recognize retrospective questions; tomorrow means review suggestions, not a forecast."""
    text = message.strip().lower()
    if not re.match(r"(?:what|why|how|show|summari[sz]e|give|review|daily review)\b", text):
        return None
    focus = None
    for pattern, name in (
        (r"\b(?:review tomorrow|tomorrow.{0,30}review)\b", "tomorrow"),
        (r"\b(?:evidence.{0,30}missing|missing evidence)\b", "evidence"),
        (r"\bmistakes?\b", "mistakes"),
        (r"\blessons?\b", "lessons"),
        (r"\b(?:perform|performance|pnl|p&l|win rate|expectancy)\b", "performance"),
        (r"\bblocked\b", "blocked"),
        (r"\bsetups?\b", "setups"),
        (r"\btrades?\b.{0,30}\b(?:did|took|taken)\b", "trades"),
        (r"\b(?:happened|daily review|day review)\b", "summary"),
    ):
        if re.search(pattern, text):
            focus = name
            break
    if focus is None:
        return None
    if re.search(r"\btomorrow\b", text) and focus != "tomorrow":
        raise ValidationAppError("Future events are unavailable; ask what to review tomorrow.")
    # General setup/performance reads retain their existing behavior unless daily-scoped.
    daily = re.search(r"\b(?:today|yesterday|daily|tomorrow)\b|\b\d{4}-\d{2}-\d{2}\b", text)
    if (
        not daily
        and focus in {"setups", "performance", "summary"}
        and text.rstrip("?!. ") not in {"what setups did we see", "what happened"}
    ):
        return None
    if re.search(
        r"\b(?:last|ago|week|month|year|monday|tuesday|wednesday|thursday|"
        r"friday|saturday|sunday)\b",
        text,
    ):
        raise ValidationAppError("Specify one calendar day as YYYY-MM-DD for a Daily Review.")
    days = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if len(days) > 1 or ("today" in text and "yesterday" in text):
        raise ValidationAppError("Daily Review reads one calendar day at a time.")
    return ActionRequest(
        name="daily_review.read",
        arguments={
            "focus": focus,
            "relative_day": "yesterday" if re.search(r"\byesterday\b", text) else "today",
            **({"day": days[0]} if days else {}),
        },
    )


def read_daily_review(
    session: Session,
    inputs: DailyReviewInput,
    *,
    organization_id: UUID,
    user_id: UUID,
    now: datetime,
) -> DailyReview:
    today = now.astimezone(ZoneInfo(inputs.timezone)).date()
    day = inputs.day or (today - timedelta(days=inputs.relative_day == "yesterday"))
    if day > today:
        raise ValidationAppError("Daily Review requires a current or past recorded day.")
    return DailyReviewService(session).review(
        organization_id=organization_id,
        user_id=user_id,
        window=daily_window(day, inputs.timezone),
        generated_at=now,
    )


_TOPICS = {
    "setups": {ReviewTopic.SETUP, ReviewTopic.MISSED},
    "trades": {ReviewTopic.PAPER_OPEN, ReviewTopic.PAPER_CLOSE},
    "blocked": {ReviewTopic.BLOCKED, ReviewTopic.RISK},
    "performance": {ReviewTopic.PAPER_CLOSE},
    "mistakes": {ReviewTopic.MISTAKE},
    "lessons": {ReviewTopic.LESSON},
    "evidence": {ReviewTopic.QUALITY},
    "tomorrow": {ReviewTopic.LESSON, ReviewTopic.MISTAKE, ReviewTopic.QUALITY},
}


def _bounded_lines(lines: list[str], budget: int) -> str:
    """Keep complete evidence lines and disclose omission; full records accompany the reply."""
    kept = []
    size = 0
    for line in lines:
        if size + len(line) + 1 > budget - 80:
            break
        kept.append(line)
        size += len(line) + 1
    if len(kept) < len(lines):
        kept.append(f"{len(lines) - len(kept)} more entries in the attached daily_review record.")
    return "\n".join(kept)


def render_daily_review(review: DailyReview, inputs: DailyReviewInput) -> str:
    """Display only service records and accounting values, preserving their classification."""
    topics = _TOPICS.get(inputs.focus)
    header = (
        f"Daily Review {review.window.day} ({review.window.timezone}); "
        f"review_id={review.review_id}.\n"
        f"Recorded snapshot generated at {review.generated_at.isoformat()}."
    )
    parts = [header]
    if inputs.focus == "summary":
        parts.append(
            "Recorded item counts (not unique trades/setups):\n"
            + _bounded_lines(
                [f"{topic.value}={count}" for topic, count in review.counts.items()], 350
            )
        )
    if inputs.focus == "tomorrow":
        parts.append(
            "Tomorrow's review suggestions use this recorded day; no forecast is available."
        )
    for label, items in (
        ("Facts", review.facts),
        ("User observations", review.user_observations),
        ("System inference", review.system_inference),
        ("Research suggestions", review.research_suggestions),
    ):
        selected = [item for item in items if topics is None or item.topic in topics]
        lines = [_item_line(item) for item in selected]
        parts.append(
            label
            + ":\n"
            + (_bounded_lines(lines, 500) if lines else "No matching recorded evidence.")
        )
    if inputs.focus in {"summary", "trades", "performance"}:
        lines = []
        for pnl in review.daily_pnl:
            sources = ", ".join(f"{s.record_type}:{s.record_id}" for s in pnl.sources[:2])
            if len(pnl.sources) > 2:
                sources += f"; {len(pnl.sources) - 2} more sources in daily_review"
            lines.append(
                f"{pnl.cohort}: recorded net PnL={pnl.recorded_net_pnl}; "
                f"complete={pnl.complete}; closes={pnl.closed_count}; "
                f"measured={pnl.measured_count}; missing={pnl.missing_pnl_count}; "
                f"win rate={pnl.win_rate}; expectancy={pnl.expectancy}; sources=[{sources}]"
            )
        parts.append(
            "Recorded paper performance (facts):\n"
            + (
                _bounded_lines(lines, 650)
                if lines
                else "Daily PnL unavailable: no recorded paper closes."
            )
        )
        parts.append(
            "None means unavailable. Incomplete PnL is a partial recorded sum. "
            "Win rate/expectancy require five measured closes with no missing PnL. "
            "Accounting units are not recorded; no cross-account total or profitability claim."
        )
    parts.append(
        "Evidence limits: absence of records does not prove inactivity. Setup/Watcher evidence "
        "is organization-wide; journal, risk and performance are user-scoped. "
        "Stored observations are not verified facts. Full source IDs, timestamps, counts, "
        "accounting and limitations accompany this reply in daily_review."
    )
    if inputs.focus == "evidence":
        parts.append(
            "Recorded coverage limitations:\n" + _bounded_lines(list(review.limitations), 550)
        )
    return "\n\n".join(parts)


def _item_line(item: ReviewItem) -> str:
    sources = ", ".join(f"{s.record_type}:{s.record_id}" for s in item.sources)
    # Quote stored words as evidence, never interpret them as instructions.
    text = f"; recorded text preview={json.dumps(item.text[:140])}" if item.text else ""
    return f"{item.topic.value}: {item.code}{text}; sources=[{sources}]"
