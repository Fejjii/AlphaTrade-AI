"""Pure deterministic coaching rules (Slice 87).

Side-effect-free pattern scoring, severity mapping, and templated prompt text.
No I/O, no LLM, no external calls. All wording is review/discipline framed.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

# Category codes mirrored as plain strings for unit tests without schema imports.
CATEGORY_MISSED_ENTRY = "missed_entry"
CATEGORY_SHOULD_HAVE_WAITED = "should_have_waited"
CATEGORY_SHOULD_HAVE_AVOIDED = "should_have_avoided"
CATEGORY_INVALIDATION_HIT = "invalidation_hit"
CATEGORY_LOW_QUALITY_SETUP = "low_quality_setup"
CATEGORY_OVERCONFIDENCE = "overconfidence"
CATEGORY_WEAK_CONFIDENCE_CORRELATION = "weak_confidence_correlation"

RELIABILITY_NONE = "none"
RELIABILITY_LOW = "low"
RELIABILITY_MEDIUM = "medium"
RELIABILITY_HIGH = "high"

SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
SEVERITY_CRITICAL = "critical"

DIRECTION_POSITIVE = "positive"
DIRECTION_NEGATIVE = "negative"
DIRECTION_NEUTRAL = "neutral"

RATE_FLOOR = 0.3
LOW_QUALITY_CEILING = 50.0
_OVERCONFIDENCE_BUCKETS = frozenset({"high", "very_high"})
_CRITICAL_CATEGORIES = frozenset({CATEGORY_SHOULD_HAVE_AVOIDED, CATEGORY_INVALIDATION_HIT})

# Wording guard — coaching must never read like trade advice.
FORBIDDEN_WORDING_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bbuy\b",
        r"\bsell\b",
        r"\bplace\s+order\b",
        r"\bplace\s+an?\s+order\b",
        r"\bexecute\b",
        r"\btake\s+this\s+trade\b",
        r"\btake\s+the\s+trade\b",
    )
)

TITLE_TEMPLATES: dict[str, str] = {
    CATEGORY_MISSED_ENTRY: "Review: missed entries on '{key}'",
    CATEGORY_SHOULD_HAVE_WAITED: "Review: entered too early on '{key}'",
    CATEGORY_SHOULD_HAVE_AVOIDED: "Review: setups to avoid on '{key}'",
    CATEGORY_INVALIDATION_HIT: "Review: invalidation frequently hit on '{key}'",
    CATEGORY_LOW_QUALITY_SETUP: "Review: low-quality setups on '{key}'",
    CATEGORY_OVERCONFIDENCE: "Review: overconfidence in '{key}' confidence setups",
    CATEGORY_WEAK_CONFIDENCE_CORRELATION: "Review: weak confidence-outcome link",
}

PROMPT_TEMPLATES: dict[str, str] = {
    CATEGORY_MISSED_ENTRY: (
        "Review this behavior: missed entries occurred in {rate_pct}% of {n} '{key}' sessions "
        "(session ids cited in source metadata). Study what prevented timely validation before "
        "grading more setups like this."
    ),
    CATEGORY_SHOULD_HAVE_WAITED: (
        "Review this behavior: {rate_pct}% of {n} '{key}' sessions were graded "
        "'should have waited'. Review your timing discipline for this pattern."
    ),
    CATEGORY_SHOULD_HAVE_AVOIDED: (
        "Review this behavior: {rate_pct}% of {n} '{key}' sessions were graded "
        "'should have avoided'. Review your filters for this condition."
    ),
    CATEGORY_INVALIDATION_HIT: (
        "Review this behavior: invalidation was hit in {rate_pct}% of {n} '{key}' sessions. "
        "Study what invalidated these setups before validating more of them."
    ),
    CATEGORY_LOW_QUALITY_SETUP: (
        "Review this behavior: setup quality scored {quality_score} over {n} '{key}' sessions. "
        "Review whether this pattern meets your validation standards."
    ),
    CATEGORY_OVERCONFIDENCE: (
        "Review this behavior: high-confidence setups succeeded only {success_pct}% over {n} "
        "sessions in the '{key}' bucket. Review whether your confidence is calibrated."
    ),
    CATEGORY_WEAK_CONFIDENCE_CORRELATION: (
        "Review this behavior: across {n} graded sessions, higher confidence did not correlate "
        "with better outcomes ({correlation_label}). Review how you assign confidence."
    ),
}


@dataclass(frozen=True)
class RawCoachingFactor:
    code: str
    label: str
    direction: str
    contribution: float
    detail: str


@dataclass(frozen=True)
class RawPattern:
    """Detected behavior pattern before templating."""

    category: str
    matched_dimension: str
    matched_key: str
    sample_size: int
    rate: float | None
    source_session_ids: tuple[str, ...] = ()
    analytics_codes: tuple[str, ...] = ()
    quality_score: float | None = None
    success_rate: float | None = None
    correlation: str | None = None


@dataclass(frozen=True)
class CoachingBuildResult:
    """Fully scored coaching prompt fields."""

    signature: str
    category: str
    title: str
    prompt_text: str
    severity: str
    reliability: str
    concern_score: int
    insufficient_data: bool
    factors: list[RawCoachingFactor] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)


def coaching_signature(*, category: str, matched_dimension: str, matched_key: str) -> str:
    """Stable dedup key for a coaching pattern."""
    payload = f"{category}|{matched_dimension}|{matched_key}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def reliability_tier(sample_size: int, min_sample: int) -> str:
    if sample_size <= 0:
        return RELIABILITY_NONE
    if sample_size < min_sample:
        return RELIABILITY_LOW
    if sample_size < 3 * min_sample:
        return RELIABILITY_MEDIUM
    return RELIABILITY_HIGH


def reliability_weight(sample_size: int, min_sample: int) -> float:
    k = max(min_sample, 1)
    if sample_size <= 0:
        return 0.0
    return sample_size / (sample_size + k)


def concern_score(*, rate: float | None, sample_size: int, min_sample: int) -> int:
    severity_weight = rate or 0.0
    reliability = reliability_weight(sample_size, min_sample)
    return round(min(100.0, max(0.0, 100.0 * severity_weight * reliability)))


def map_severity(
    *,
    category: str,
    rate: float | None,
    reliability: str,
    sample_size: int,
    min_sample: int,
) -> str | None:
    """Map a pattern to severity, or None when it must not be emitted."""
    if sample_size < min_sample or rate is None or rate < RATE_FLOOR:
        return None
    if reliability in (RELIABILITY_NONE, RELIABILITY_LOW):
        return None
    if reliability == RELIABILITY_MEDIUM:
        return SEVERITY_MEDIUM
    if rate >= 0.7 and category in _CRITICAL_CATEGORIES:
        return SEVERITY_CRITICAL
    if rate >= 0.5:
        return SEVERITY_HIGH
    return SEVERITY_MEDIUM


def contains_forbidden_wording(text: str) -> bool:
    return any(pattern.search(text) for pattern in FORBIDDEN_WORDING_PATTERNS)


def build_coaching_prompt(pattern: RawPattern, *, min_sample: int) -> CoachingBuildResult | None:
    """Build a scored coaching prompt from a raw pattern, or None if gated out."""
    reliability = reliability_tier(pattern.sample_size, min_sample)
    insufficient = pattern.sample_size < min_sample or pattern.rate is None
    severity = map_severity(
        category=pattern.category,
        rate=pattern.rate,
        reliability=reliability,
        sample_size=pattern.sample_size,
        min_sample=min_sample,
    )
    if severity is None:
        return None

    rate_pct = round((pattern.rate or 0.0) * 100)
    success_pct = round((pattern.success_rate or 0.0) * 100)
    title = TITLE_TEMPLATES[pattern.category].format(key=pattern.matched_key)
    prompt_text = _format_prompt_text(pattern, rate_pct=rate_pct, success_pct=success_pct)
    score = concern_score(rate=pattern.rate, sample_size=pattern.sample_size, min_sample=min_sample)
    factors = _build_factors(pattern, min_sample=min_sample, reliability=reliability)
    rationale = _build_rationale(pattern, reliability=reliability, min_sample=min_sample)

    for text in (title, prompt_text, *rationale):
        if contains_forbidden_wording(text):
            raise ValueError(f"Forbidden coaching wording detected: {text[:80]}")

    return CoachingBuildResult(
        signature=coaching_signature(
            category=pattern.category,
            matched_dimension=pattern.matched_dimension,
            matched_key=pattern.matched_key,
        ),
        category=pattern.category,
        title=title,
        prompt_text=prompt_text,
        severity=severity,
        reliability=reliability,
        concern_score=score,
        insufficient_data=insufficient,
        factors=factors,
        rationale=rationale,
    )


def _format_prompt_text(pattern: RawPattern, *, rate_pct: int, success_pct: int) -> str:
    key = pattern.matched_key
    n = pattern.sample_size
    if pattern.category == CATEGORY_LOW_QUALITY_SETUP:
        return PROMPT_TEMPLATES[pattern.category].format(
            key=key,
            n=n,
            quality_score=round(pattern.quality_score or 0.0, 1),
        )
    if pattern.category == CATEGORY_OVERCONFIDENCE:
        return PROMPT_TEMPLATES[pattern.category].format(
            key=key,
            n=n,
            success_pct=success_pct,
        )
    if pattern.category == CATEGORY_WEAK_CONFIDENCE_CORRELATION:
        correlation_label = {
            "none": "no clear link",
            "negative": "an inverse link",
        }.get(pattern.correlation or "none", "no clear link")
        return PROMPT_TEMPLATES[pattern.category].format(
            n=n,
            correlation_label=correlation_label,
        )
    return PROMPT_TEMPLATES[pattern.category].format(key=key, n=n, rate_pct=rate_pct)


def _build_factors(
    pattern: RawPattern, *, min_sample: int, reliability: str
) -> list[RawCoachingFactor]:
    factors: list[RawCoachingFactor] = []
    if pattern.rate is not None:
        factors.append(
            RawCoachingFactor(
                code="pattern_rate",
                label="Pattern frequency",
                direction=DIRECTION_NEGATIVE,
                contribution=round(pattern.rate * 100, 2),
                detail=f"Behavior recurred in {round(pattern.rate * 100)}% of matched sessions.",
            )
        )
    weight = reliability_weight(pattern.sample_size, min_sample)
    if 0.0 < weight < 1.0:
        factors.append(
            RawCoachingFactor(
                code="sample_shrinkage",
                label="Sample shrinkage",
                direction=DIRECTION_NEUTRAL,
                contribution=0.0,
                detail=(
                    f"Only {pattern.sample_size} session(s); concern score is tempered until "
                    f"at least {min_sample} are available."
                ),
            )
        )
    if reliability in (RELIABILITY_MEDIUM, RELIABILITY_HIGH):
        factors.append(
            RawCoachingFactor(
                code="reliability",
                label="Evidence reliability",
                direction=(
                    DIRECTION_POSITIVE if reliability == RELIABILITY_HIGH else DIRECTION_NEUTRAL
                ),
                contribution=round(weight * 100, 2),
                detail=f"Reliability tier: {reliability}.",
            )
        )
    if pattern.analytics_codes:
        factors.append(
            RawCoachingFactor(
                code="analytics_codes",
                label="Analytics signals",
                direction=DIRECTION_NEUTRAL,
                contribution=0.0,
                detail=f"Linked analytics codes: {', '.join(pattern.analytics_codes)}.",
            )
        )
    return factors


def _build_rationale(pattern: RawPattern, *, reliability: str, min_sample: int) -> list[str]:
    rationale: list[str] = []
    if pattern.sample_size < 3 * min_sample:
        rationale.append(
            f"Based on {pattern.sample_size} session(s); more validation data strengthens this "
            "pattern."
        )
    if pattern.source_session_ids:
        rationale.append(
            f"Source session ids: {', '.join(pattern.source_session_ids[:5])}"
            + (" …" if len(pattern.source_session_ids) > 5 else "")
            + "."
        )
    if reliability == RELIABILITY_MEDIUM:
        rationale.append("Severity is capped at medium until sample size reaches high reliability.")
    return rationale
