"""Pure scoring helpers for validation prioritization (Slice 85).

Deterministic, side-effect-free functions kept separate from I/O so they can be
unit-tested in isolation. No LLM authority, no external calls, no automation.
The output is human study guidance only and never an execution instruction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Action labels and reliability tiers are mirrored as plain strings here so this
# module stays free of the pydantic/schema layer. The service maps them to the
# corresponding StrEnum members.
ACTION_PRIORITIZE = "prioritize"
ACTION_WATCH = "watch"
ACTION_COLLECT_MORE_DATA = "collect_more_data"
ACTION_AVOID_FOR_NOW = "avoid_for_now"

RELIABILITY_NONE = "none"
RELIABILITY_LOW = "low"
RELIABILITY_MEDIUM = "medium"
RELIABILITY_HIGH = "high"

DIRECTION_POSITIVE = "positive"
DIRECTION_NEGATIVE = "negative"
DIRECTION_NEUTRAL = "neutral"

# Action thresholds. Applied only when reliability is medium/high.
_AVOID_SCORE_CEILING = 40
_PRIORITIZE_SCORE_FLOOR = 70
_AVOID_INVALIDATION_RATE = 0.5
_AVOID_SHOULD_HAVE_AVOIDED_RATE = 0.3

_HIGH_CONFIDENCE_BUCKETS = frozenset({"high", "very_high"})


@dataclass(frozen=True)
class PriorityWeights:
    """Weights for the validation priority blend. Configurable, not magic."""

    prior: float = 50.0
    w_invalidation: float = 25.0
    w_should_have_avoided: float = 30.0
    b_confidence_alignment: float = 10.0
    b_readiness: float = 8.0


PRIORITY_WEIGHTS = PriorityWeights()


@dataclass(frozen=True)
class HistoryStats:
    """Historical performance for the dimension group matched to an item."""

    sample_size: int = 0
    quality_score: float | None = None
    success_rate: float | None = None
    invalidation_hit_rate: float | None = None
    should_have_avoided_rate: float | None = None


@dataclass(frozen=True)
class ItemContext:
    """Current setup context for a pending item."""

    confidence: float | None = None
    confidence_bucket: str | None = None
    readiness: float = 0.0


@dataclass(frozen=True)
class RawFactor:
    """Explainable contributor to the priority score, relative to the prior."""

    code: str
    label: str
    direction: str
    contribution: float
    detail: str


@dataclass(frozen=True)
class PriorityBreakdown:
    """Full deterministic scoring result for one pending item."""

    score: int
    action_label: str
    reliability: str
    factors: list[RawFactor] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)


def reliability_tier(sample_size: int, min_sample: int) -> str:
    """Map a matched sample size to a reliability tier."""
    if sample_size <= 0:
        return RELIABILITY_NONE
    if sample_size < min_sample:
        return RELIABILITY_LOW
    if sample_size < 3 * min_sample:
        return RELIABILITY_MEDIUM
    return RELIABILITY_HIGH


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _reliability_weight(sample_size: int, min_sample: int) -> float:
    """Shrinkage weight r = n / (n + k); thin history is pulled toward the prior."""
    k = max(min_sample, 1)
    if sample_size <= 0:
        return 0.0
    return sample_size / (sample_size + k)


def compute_priority(
    history: HistoryStats,
    context: ItemContext,
    *,
    min_sample: int,
    confidence_correlation: str,
    weights: PriorityWeights = PRIORITY_WEIGHTS,
) -> PriorityBreakdown:
    """Compute a deterministic 0-100 validation priority for a pending item.

    Blends shrinkage-adjusted historical quality with current setup context.
    Penalizes repeated invalidations and 'should have avoided' history; rewards
    confidence that historically aligns with success and checklist readiness.
    """
    n = history.sample_size
    r = _reliability_weight(n, min_sample)
    prior = weights.prior

    has_history = n > 0 and history.quality_score is not None
    observed_quality = history.quality_score if has_history else prior
    effective_quality = r * observed_quality + (1.0 - r) * prior

    invalidation_rate = history.invalidation_hit_rate or 0.0
    avoided_rate = history.should_have_avoided_rate or 0.0
    invalidation_penalty = weights.w_invalidation * invalidation_rate * r
    avoided_penalty = weights.w_should_have_avoided * avoided_rate * r

    confidence_aligned = (
        confidence_correlation == "positive"
        and context.confidence_bucket in _HIGH_CONFIDENCE_BUCKETS
    )
    confidence_boost = weights.b_confidence_alignment if confidence_aligned else 0.0
    readiness_boost = weights.b_readiness * _clamp(context.readiness, 0.0, 1.0)

    raw = (
        effective_quality
        - invalidation_penalty
        - avoided_penalty
        + confidence_boost
        + readiness_boost
    )
    score = round(_clamp(raw, 0.0, 100.0))

    reliability = reliability_tier(n, min_sample)
    factors = _build_factors(
        prior=prior,
        effective_quality=effective_quality,
        reliability_weight=r,
        sample_size=n,
        invalidation_rate=invalidation_rate,
        invalidation_penalty=invalidation_penalty,
        avoided_rate=avoided_rate,
        avoided_penalty=avoided_penalty,
        confidence_boost=confidence_boost,
        readiness_boost=readiness_boost,
        context=context,
    )
    action_label = _decide_action(
        score=score,
        reliability=reliability,
        invalidation_rate=invalidation_rate,
        avoided_rate=avoided_rate,
    )
    rationale = _build_rationale(
        action_label=action_label,
        reliability=reliability,
        sample_size=n,
        min_sample=min_sample,
        invalidation_rate=invalidation_rate,
        avoided_rate=avoided_rate,
        confidence_aligned=confidence_aligned,
    )
    return PriorityBreakdown(
        score=score,
        action_label=action_label,
        reliability=reliability,
        factors=factors,
        rationale=rationale,
    )


def _build_factors(
    *,
    prior: float,
    effective_quality: float,
    reliability_weight: float,
    sample_size: int,
    invalidation_rate: float,
    invalidation_penalty: float,
    avoided_rate: float,
    avoided_penalty: float,
    confidence_boost: float,
    readiness_boost: float,
    context: ItemContext,
) -> list[RawFactor]:
    factors: list[RawFactor] = []

    quality_delta = round(effective_quality - prior, 2)
    if quality_delta:
        factors.append(
            RawFactor(
                code="historical_quality",
                label="Historical setup quality",
                direction=DIRECTION_POSITIVE if quality_delta > 0 else DIRECTION_NEGATIVE,
                contribution=quality_delta,
                detail=(
                    f"Matched history quality resolves to {round(effective_quality, 1)} "
                    f"(neutral baseline {round(prior)})."
                ),
            )
        )

    if 0.0 < reliability_weight < 1.0:
        factors.append(
            RawFactor(
                code="low_sample_shrinkage",
                label="Low-sample shrinkage",
                direction=DIRECTION_NEUTRAL,
                contribution=0.0,
                detail=(
                    f"Only {sample_size} matched session(s); the score is pulled toward the "
                    "neutral baseline until more evidence exists."
                ),
            )
        )

    if invalidation_penalty:
        factors.append(
            RawFactor(
                code="invalidation_penalty",
                label="Repeated invalidations",
                direction=DIRECTION_NEGATIVE,
                contribution=-round(invalidation_penalty, 2),
                detail=(
                    f"Invalidation was hit in {round(invalidation_rate * 100)}% of "
                    "matched sessions."
                ),
            )
        )

    if avoided_penalty:
        factors.append(
            RawFactor(
                code="should_have_avoided_penalty",
                label="Should-have-avoided history",
                direction=DIRECTION_NEGATIVE,
                contribution=-round(avoided_penalty, 2),
                detail=(
                    f"{round(avoided_rate * 100)}% of matched sessions were graded "
                    "'should have avoided'."
                ),
            )
        )

    if confidence_boost:
        factors.append(
            RawFactor(
                code="confidence_alignment",
                label="Confidence aligns with success",
                direction=DIRECTION_POSITIVE,
                contribution=round(confidence_boost, 2),
                detail=(
                    "Higher confidence historically correlates with success and this setup is "
                    f"'{context.confidence_bucket}' confidence."
                ),
            )
        )

    if readiness_boost:
        factors.append(
            RawFactor(
                code="readiness",
                label="Preparation readiness",
                direction=DIRECTION_POSITIVE,
                contribution=round(readiness_boost, 2),
                detail=f"Checklist/prep readiness at {round(context.readiness * 100)}%.",
            )
        )

    return factors


def _decide_action(
    *,
    score: int,
    reliability: str,
    invalidation_rate: float,
    avoided_rate: float,
) -> str:
    if reliability in (RELIABILITY_NONE, RELIABILITY_LOW):
        return ACTION_COLLECT_MORE_DATA
    if (
        avoided_rate >= _AVOID_SHOULD_HAVE_AVOIDED_RATE
        or invalidation_rate >= _AVOID_INVALIDATION_RATE
        or score < _AVOID_SCORE_CEILING
    ):
        return ACTION_AVOID_FOR_NOW
    if score >= _PRIORITIZE_SCORE_FLOOR:
        return ACTION_PRIORITIZE
    return ACTION_WATCH


def _build_rationale(
    *,
    action_label: str,
    reliability: str,
    sample_size: int,
    min_sample: int,
    invalidation_rate: float,
    avoided_rate: float,
    confidence_aligned: bool,
) -> list[str]:
    rationale: list[str] = []
    if action_label == ACTION_COLLECT_MORE_DATA:
        rationale.append(
            f"Only {sample_size} matched session(s) (min {min_sample}); validate more to build "
            "reliable evidence."
        )
        if avoided_rate > 0:
            rationale.append("Caution: some matched sessions were graded 'should have avoided'.")
    elif action_label == ACTION_AVOID_FOR_NOW:
        if avoided_rate >= _AVOID_SHOULD_HAVE_AVOIDED_RATE:
            rationale.append("Frequently graded 'should have avoided' in matched history.")
        if invalidation_rate >= _AVOID_INVALIDATION_RATE:
            rationale.append("Invalidation is hit often for this kind of setup.")
        if not rationale:
            rationale.append("Weak historical quality for this kind of setup.")
    elif action_label == ACTION_PRIORITIZE:
        rationale.append("Strong historical quality with sufficient evidence.")
        if confidence_aligned:
            rationale.append("Confidence historically aligns with success here.")
    else:  # watch
        rationale.append("Moderate historical quality; reasonable but not a standout.")
    return rationale
