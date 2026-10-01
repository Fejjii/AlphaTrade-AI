"""Read-only daily review contracts; no narrative can grant trading authority."""

from __future__ import annotations

from datetime import date, timedelta
from enum import StrEnum
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, model_validator

from app.market_contracts.models import CanonicalDecimal, CanonicalModel


class ReviewClass(StrEnum):
    FACT = "fact"
    USER_OBSERVATION = "user_observation"
    SYSTEM_INFERENCE = "system_inference"
    RESEARCH_SUGGESTION = "research_suggestion"


class ReviewTopic(StrEnum):
    WATCHER = "watcher_activity"
    SETUP = "setups"
    PAPER_OPEN = "paper_opened"
    PAPER_CLOSE = "paper_closed"
    BLOCKED = "blocked_candidates"
    RISK = "risk_events"
    JOURNAL = "journal_entries"
    MISTAKE = "mistakes"
    LESSON = "lessons"
    MISSED = "missed_setups"
    STRATEGY = "strategy_observations"
    QUALITY = "data_quality_limitations"


class ReviewWindow(CanonicalModel):
    day: date
    timezone: str
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def validate_day(self) -> ReviewWindow:
        zone = ZoneInfo(self.timezone)
        local_start = self.start.astimezone(zone)
        local_end = self.end.astimezone(zone)
        if (
            local_start.date() != self.day
            or local_start.time().isoformat() != "00:00:00"
            or local_end.date() != self.day + timedelta(days=1)
            or local_end.time().isoformat() != "00:00:00"
        ):
            raise ValueError("Window must span exactly one local calendar day.")
        return self


class ReviewSource(CanonicalModel):
    record_type: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    occurred_at: AwareDatetime
    version: int | None = Field(default=None, ge=1)
    content_hash: str | None = None
    upstream_system: str | None = None
    upstream_event_id: str | None = None


class ReviewItem(CanonicalModel):
    topic: ReviewTopic
    classification: ReviewClass
    code: str = Field(min_length=1)
    text: str | None = None
    sources: tuple[ReviewSource, ...] = Field(min_length=1)
    candidate_id: UUID | None = None
    strategy_version_id: UUID | None = None


class PaperClose(CanonicalModel):
    """Only the scoped adapter may select authoritative paper journal closes."""

    source: ReviewSource
    cohort: str
    net_pnl: CanonicalDecimal | None = None


class ReviewInput(CanonicalModel):
    organization_id: UUID
    user_id: UUID
    window: ReviewWindow
    items: tuple[ReviewItem, ...] = ()
    closes: tuple[PaperClose, ...] = ()
    limitations: tuple[str, ...] = ()


class DailyPnl(CanonicalModel):
    cohort: str
    closed_count: int
    measured_count: int
    missing_pnl_count: int
    recorded_net_pnl: CanonicalDecimal | None
    complete: bool
    wins: int
    losses: int
    breakeven: int
    minimum_sample: int
    win_rate: CanonicalDecimal | None
    expectancy: CanonicalDecimal | None
    sources: tuple[ReviewSource, ...]


class DailyReview(CanonicalModel):
    schema_version: Literal["DailyReview/v1"] = "DailyReview/v1"
    review_id: UUID
    content_hash: str
    organization_id: UUID
    user_id: UUID
    window: ReviewWindow
    generated_at: AwareDatetime
    facts: tuple[ReviewItem, ...]
    user_observations: tuple[ReviewItem, ...]
    system_inference: tuple[ReviewItem, ...]
    research_suggestions: tuple[ReviewItem, ...]
    counts: dict[ReviewTopic, int]
    daily_pnl: tuple[DailyPnl, ...]
    limitations: tuple[str, ...]
    live_executable: Literal[False] = False
    telegram_delivery: Literal[False] = False
