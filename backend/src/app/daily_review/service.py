"""Deterministic daily review reduction. Pure reads, no clock or market calls."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, localcontext
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from app.daily_review.contracts import (
    DailyPnl,
    DailyReview,
    PaperClose,
    ReviewClass,
    ReviewInput,
    ReviewItem,
    ReviewTopic,
    ReviewWindow,
)
from app.services.canonical_serialization import canonical_sha256

MINIMUM_SAMPLE = 5  # Matches the existing paper-evaluation provisional threshold.


def daily_window(day: date, timezone: str = "UTC") -> ReviewWindow:
    zone = ZoneInfo(timezone)
    return ReviewWindow(
        day=day,
        timezone=timezone,
        start=datetime.combine(day, time.min, zone).astimezone(UTC),
        end=datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC),
    )


def build_review(data: ReviewInput, *, generated_at: datetime) -> DailyReview:
    """Identical snapshots yield identical identity regardless of input order/clock.

    Half-open occurrence windows exclude next-day records. Duplicate copies converge;
    conflicting copies of one item or close fail rather than selecting arbitrary facts.
    """
    window = data.window
    items: dict[str, ReviewItem] = {}
    for item in data.items:
        if not all(window.start <= s.occurred_at < window.end for s in item.sources):
            continue
        key = canonical_sha256(
            {
                "topic": item.topic,
                "classification": item.classification,
                "code": item.code,
                "sources": [(s.record_type, s.record_id, s.version) for s in item.sources],
            }
        )
        if key in items and items[key] != item:
            raise ValueError("Conflicting review source identity.")
        items[key] = item
    ordered = tuple(sorted(items.values(), key=canonical_sha256))
    closes: dict[tuple[str, str], PaperClose] = {}
    for close in data.closes:
        if not window.start <= close.source.occurred_at < window.end:
            continue
        close_key = (close.source.record_type, close.source.record_id)
        if close_key in closes and closes[close_key] != close:
            raise ValueError("Conflicting paper close identity.")
        closes[close_key] = close
    pnl = []
    for cohort in sorted({c.cohort for c in closes.values()}):
        group = sorted(
            (c for c in closes.values() if c.cohort == cohort), key=lambda c: c.source.record_id
        )
        values = [c.net_pnl for c in group if c.net_pnl is not None]
        missing = len(group) - len(values)
        permits = len(values) >= MINIMUM_SAMPLE and missing == 0
        # Do not depend on a caller's ambient decimal precision.
        with localcontext() as context:
            context.prec = 50
            total = sum(values, Decimal(0)) if values else None
            wins = sum(v > 0 for v in values)
            pnl.append(
                DailyPnl(
                    cohort=cohort,
                    closed_count=len(group),
                    measured_count=len(values),
                    missing_pnl_count=missing,
                    recorded_net_pnl=total,
                    complete=missing == 0,
                    wins=wins,
                    losses=sum(v < 0 for v in values),
                    breakeven=sum(v == 0 for v in values),
                    minimum_sample=MINIMUM_SAMPLE,
                    win_rate=Decimal(wins) / len(values) if permits else None,
                    expectancy=total / len(values) if permits and total is not None else None,
                    sources=tuple(c.source for c in group),
                )
            )
    limitations = set(data.limitations)
    limitations.add(
        "Absence of records does not establish absence of activity or market conditions."
    )
    limitations.add(
        "PnL is recorded realized net PnL only; no mark-to-market or counterfactual profit."
    )
    limitations.add(
        "Win rate and expectancy require five measured closes and no missing PnL; "
        "they describe this day's sample, not proven profitability."
    )
    if not closes:
        limitations.add(
            "No authoritative paper closes recorded in this window; daily PnL unavailable."
        )
    body = {
        "organization_id": data.organization_id,
        "user_id": data.user_id,
        "window": window,
        "facts": tuple(i for i in ordered if i.classification == ReviewClass.FACT),
        "user_observations": tuple(
            i for i in ordered if i.classification == ReviewClass.USER_OBSERVATION
        ),
        "system_inference": tuple(
            i for i in ordered if i.classification == ReviewClass.SYSTEM_INFERENCE
        ),
        "research_suggestions": tuple(
            i for i in ordered if i.classification == ReviewClass.RESEARCH_SUGGESTION
        ),
        "counts": {t: sum(i.topic == t for i in ordered) for t in ReviewTopic},
        "daily_pnl": tuple(pnl),
        "limitations": tuple(sorted(limitations)),
    }
    snapshot = DailyReview.model_validate(
        {
            **body,
            "content_hash": "0" * 64,
            "review_id": UUID(int=0),
            "generated_at": generated_at,
        }
    )
    hash_body = snapshot.model_dump(exclude={"generated_at", "content_hash", "review_id"})
    hash_body["window"]["day"] = window.day.isoformat()
    with localcontext() as context:
        context.prec = 50
        digest = canonical_sha256(hash_body)
    return snapshot.model_copy(
        update={
            "content_hash": digest,
            "review_id": uuid5(NAMESPACE_URL, f"alphatrade:daily-review:v1:{digest}"),
        }
    )
