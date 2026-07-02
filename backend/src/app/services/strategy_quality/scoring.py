"""Pure scoring helpers for strategy quality and detector performance (Slice 89).

Deterministic, side-effect-free functions kept separate from I/O so they can be
unit-tested in isolation. No LLM authority, no external calls, no automation.
Output is human study guidance only and never an execution instruction, a rule
change, or a live-trade recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.learning_analytics.scoring import QUALITY_WEIGHTS, QualityWeights, quality_score
from app.services.validation_priority.scoring import reliability_tier

# Trust tiers and verdicts are mirrored as plain strings here so this module
# stays free of the pydantic/schema layer. The service maps them to StrEnums.
TRUST_NONE = "none"
TRUST_LOW = "low"
TRUST_MEDIUM = "medium"
TRUST_HIGH = "high"

VERDICT_TRUSTED = "trusted"
VERDICT_WATCH = "watch"
VERDICT_IMPROVE = "improve"
VERDICT_AVOID_FOR_NOW = "avoid_for_now"
VERDICT_NEEDS_MORE_VALIDATION = "needs_more_validation"

CALIB_WELL = "well_calibrated"
CALIB_OVERCONFIDENT = "overconfident"
CALIB_UNDERCONFIDENT = "underconfident"
CALIB_INSUFFICIENT = "insufficient_data"

DIRECTION_POSITIVE = "positive"
DIRECTION_NEGATIVE = "negative"
DIRECTION_NEUTRAL = "neutral"

# Neutral quality baseline that thin detectors are shrunk toward.
QUALITY_PRIOR = 50.0

# Verdict thresholds. Applied to the shrunk quality; avoid/trusted floors mirror
# the validation priority thresholds for cross-slice consistency.
AVOID_QUALITY_CEILING = 40.0
IMPROVE_QUALITY_CEILING = 55.0
TRUSTED_QUALITY_FLOOR = 70.0
AVOID_INVALIDATION_RATE = 0.5
AVOID_SHOULD_HAVE_AVOIDED_RATE = 0.3

# Warning thresholds.
LOW_SUCCESS_CEILING = 0.4
MISSED_ENTRY_FLOOR = 0.3

# Absolute gap between mean confidence and mean success rate that flags a
# detector as over/under-confident.
CALIBRATION_TOLERANCE = 0.15

_SUFFICIENT_TIERS = frozenset({TRUST_MEDIUM, TRUST_HIGH})


@dataclass(frozen=True)
class RawDetectorFactor:
    """Explainable contributor to a detector's quality score."""

    code: str
    label: str
    direction: str
    contribution: float
    detail: str


@dataclass(frozen=True)
class RawWarning:
    """A read-only caution about a detector."""

    code: str
    message: str
    severity: str


@dataclass(frozen=True)
class DetectorScore:
    """Full deterministic scoring result for one detector."""

    trust_tier: str
    verdict: str
    raw_quality: float | None
    shrunk_quality: float | None
    factors: list[RawDetectorFactor] = field(default_factory=list)
    warnings: list[RawWarning] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)


def _reliability_weight(sample_size: int, min_sample: int) -> float:
    """Shrinkage weight r = n / (n + k); thin history is pulled toward the prior."""
    k = max(min_sample, 1)
    if sample_size <= 0:
        return 0.0
    return sample_size / (sample_size + k)


def shrink_toward_prior(
    quality: float | None,
    sample_size: int,
    min_sample: int,
    *,
    prior: float = QUALITY_PRIOR,
) -> float | None:
    """Pull a raw quality score toward the neutral prior based on sample size.

    Returns None when there is no sample at all so thin detectors never present
    a fabricated score.
    """
    if sample_size <= 0 or quality is None:
        return None
    r = _reliability_weight(sample_size, min_sample)
    return round(r * quality + (1.0 - r) * prior, 2)


def normalize_confidence(confidence: float | None) -> float | None:
    """Normalize a stored confidence to the 0-1 range used by the bucket helper.

    Detector confidence is persisted on a 0-100 scale (from the analysis engine)
    while the shared confidence bucketing expects 0-1, so anything above 1 is
    treated as a percentage. Out-of-range values are clamped defensively.
    """
    if confidence is None:
        return None
    value = confidence / 100.0 if confidence > 1.0 else confidence
    return max(0.0, min(1.0, value))


def mean_confidence(confidences: list[float | None]) -> float | None:
    """Mean of the normalized, non-null confidences, or None when none exist."""
    values = [c for c in (normalize_confidence(c) for c in confidences) if c is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def calibration_label(
    mean_conf: float | None,
    mean_success_rate: float | None,
    sample_size: int,
    min_sample: int,
) -> str:
    """Label detector confidence versus its actual success rate.

    Overconfident when confidence meaningfully exceeds success; underconfident
    when success exceeds confidence; otherwise well calibrated. Gated behind the
    sample threshold so thin detectors are never labelled.
    """
    if mean_conf is None or mean_success_rate is None or sample_size < min_sample:
        return CALIB_INSUFFICIENT
    gap = mean_conf - mean_success_rate
    if gap > CALIBRATION_TOLERANCE:
        return CALIB_OVERCONFIDENT
    if gap < -CALIBRATION_TOLERANCE:
        return CALIB_UNDERCONFIDENT
    return CALIB_WELL


def decide_verdict(
    *,
    trust_tier: str,
    shrunk_quality: float | None,
    invalidation_rate: float,
    avoided_rate: float,
) -> str:
    """Map trust and quality into a study guidance verdict.

    Thin evidence always yields 'needs_more_validation' so a detector is never
    condemned or trusted on a small sample. Only medium/high trust detectors can
    be graded 'trusted' or 'avoid_for_now'.
    """
    if trust_tier not in _SUFFICIENT_TIERS or shrunk_quality is None:
        return VERDICT_NEEDS_MORE_VALIDATION
    if (
        invalidation_rate >= AVOID_INVALIDATION_RATE
        or avoided_rate >= AVOID_SHOULD_HAVE_AVOIDED_RATE
        or shrunk_quality < AVOID_QUALITY_CEILING
    ):
        return VERDICT_AVOID_FOR_NOW
    if shrunk_quality >= TRUSTED_QUALITY_FLOOR:
        return VERDICT_TRUSTED
    if shrunk_quality < IMPROVE_QUALITY_CEILING:
        return VERDICT_IMPROVE
    return VERDICT_WATCH


def build_factors(
    *,
    success_rate: float,
    behaved_rate: float,
    invalidation_hit_rate: float,
    avoided_rate: float,
    raw_quality: float,
    shrunk_quality: float,
    sample_size: int,
    min_sample: int,
    weights: QualityWeights = QUALITY_WEIGHTS,
) -> list[RawDetectorFactor]:
    """Decompose the quality score into explainable contributions.

    The first three contributions plus the avoided penalty reconstruct the raw
    quality; the shrinkage adjustment then explains the pull toward the prior.
    """
    factors: list[RawDetectorFactor] = [
        RawDetectorFactor(
            code="success_rate",
            label="Validated success rate",
            direction=DIRECTION_POSITIVE,
            contribution=round(100.0 * weights.success * success_rate, 2),
            detail=f"{round(success_rate * 100)}% of results were graded success.",
        ),
        RawDetectorFactor(
            code="expected_behavior",
            label="Behaved as expected",
            direction=DIRECTION_POSITIVE,
            contribution=round(100.0 * weights.behaved * behaved_rate, 2),
            detail=f"{round(behaved_rate * 100)}% of results behaved as expected.",
        ),
        RawDetectorFactor(
            code="invalidation_avoidance",
            label="Invalidation avoidance",
            direction=DIRECTION_POSITIVE,
            contribution=round(
                100.0 * weights.invalidation_avoided * (1.0 - invalidation_hit_rate), 2
            ),
            detail=f"Invalidation was hit in {round(invalidation_hit_rate * 100)}% of results.",
        ),
    ]
    if avoided_rate > 0:
        factors.append(
            RawDetectorFactor(
                code="should_have_avoided_penalty",
                label="Should-have-avoided penalty",
                direction=DIRECTION_NEGATIVE,
                contribution=-round(weights.avoided_penalty * avoided_rate, 2),
                detail=(
                    f"{round(avoided_rate * 100)}% of results were graded 'should have avoided'."
                ),
            )
        )
    shrink_delta = round(shrunk_quality - raw_quality, 2)
    if shrink_delta and 0 < _reliability_weight(sample_size, min_sample) < 1.0:
        factors.append(
            RawDetectorFactor(
                code="low_sample_shrinkage",
                label="Low-sample shrinkage",
                direction=DIRECTION_NEUTRAL,
                contribution=shrink_delta,
                detail=(
                    f"Only {sample_size} result(s); the score is pulled toward the neutral "
                    f"baseline {round(QUALITY_PRIOR)} until more evidence exists."
                ),
            )
        )
    return factors


def build_warnings(
    *,
    condition: str,
    sample_size: int,
    min_sample: int,
    trust_tier: str,
    invalidation_hit_rate: float,
    avoided_rate: float,
    success_rate: float | None,
    missed_entry_rate: float | None,
    calibration: str,
) -> list[RawWarning]:
    """Derive read-only caution labels for a detector."""
    warnings: list[RawWarning] = []
    if sample_size < min_sample:
        warnings.append(
            RawWarning(
                code="insufficient_data",
                message=(
                    f"Only {sample_size} validated result(s) for '{condition}' "
                    f"(min {min_sample}); treat quality as unproven."
                ),
                severity="info",
            )
        )
    if trust_tier not in _SUFFICIENT_TIERS:
        return warnings

    if invalidation_hit_rate >= AVOID_INVALIDATION_RATE:
        warnings.append(
            RawWarning(
                code="noisy_high_invalidation",
                message=f"'{condition}' hits invalidation frequently; it is noisy.",
                severity="warning",
            )
        )
    if avoided_rate >= AVOID_SHOULD_HAVE_AVOIDED_RATE:
        warnings.append(
            RawWarning(
                code="frequently_should_have_avoided",
                message=f"'{condition}' is often graded 'should have avoided'.",
                severity="warning",
            )
        )
    if success_rate is not None and success_rate < LOW_SUCCESS_CEILING:
        warnings.append(
            RawWarning(
                code="low_success_sufficient_sample",
                message=f"'{condition}' has a low success rate on a sufficient sample.",
                severity="warning",
            )
        )
    if missed_entry_rate is not None and missed_entry_rate >= MISSED_ENTRY_FLOOR:
        warnings.append(
            RawWarning(
                code="missed_entry_prone",
                message=f"'{condition}' frequently ends in missed entries.",
                severity="warning",
            )
        )
    if calibration == CALIB_OVERCONFIDENT:
        warnings.append(
            RawWarning(
                code="overconfident_detector",
                message=f"'{condition}' confidence runs higher than its actual success rate.",
                severity="warning",
            )
        )
    elif calibration == CALIB_UNDERCONFIDENT:
        warnings.append(
            RawWarning(
                code="underconfident_detector",
                message=f"'{condition}' succeeds more often than its confidence suggests.",
                severity="info",
            )
        )
    return warnings


def build_rationale(
    *,
    verdict: str,
    condition: str,
    sample_size: int,
    min_sample: int,
    invalidation_rate: float,
    avoided_rate: float,
    success_rate: float | None,
) -> list[str]:
    """Human-readable justification for a detector's verdict."""
    rationale: list[str] = []
    if verdict == VERDICT_NEEDS_MORE_VALIDATION:
        rationale.append(
            f"Only {sample_size} validated result(s) (min {min_sample}); validate '{condition}' "
            "more to build reliable evidence."
        )
    elif verdict == VERDICT_AVOID_FOR_NOW:
        if invalidation_rate >= AVOID_INVALIDATION_RATE:
            rationale.append("Invalidation is hit often for this detector.")
        if avoided_rate >= AVOID_SHOULD_HAVE_AVOIDED_RATE:
            rationale.append("Frequently graded 'should have avoided' in validated history.")
        if not rationale:
            rationale.append("Weak validated quality for this detector.")
    elif verdict == VERDICT_TRUSTED:
        rationale.append("Strong validated quality with sufficient evidence.")
        if success_rate is not None:
            rationale.append(
                f"Success rate of {round(success_rate * 100)}% across validated results."
            )
    elif verdict == VERDICT_IMPROVE:
        rationale.append("Sufficient evidence but weak quality; conditions likely need refinement.")
    else:  # watch
        rationale.append("Moderate validated quality; reasonable but not a standout.")
    return rationale


def score_detector(
    *,
    condition: str,
    sample_size: int,
    success_rate: float | None,
    behaved_rate: float | None,
    invalidation_hit_rate: float | None,
    avoided_rate: float | None,
    missed_entry_rate: float | None,
    mean_conf: float | None,
    calibration: str,
    min_sample: int,
) -> DetectorScore:
    """Compose trust tier, verdict, quality, factors, warnings, and rationale.

    All rate inputs may be None (no sample); they are treated as 0 for scoring
    but the resulting quality is None whenever there is no sample.
    """
    trust_tier = reliability_tier(sample_size, min_sample)
    success = success_rate or 0.0
    behaved = behaved_rate or 0.0
    invalidation = invalidation_hit_rate or 0.0
    avoided = avoided_rate or 0.0

    raw_quality: float | None = None
    shrunk_quality: float | None = None
    factors: list[RawDetectorFactor] = []
    if sample_size > 0:
        raw_quality = quality_score(success, behaved, invalidation, avoided)
        shrunk_quality = shrink_toward_prior(raw_quality, sample_size, min_sample)
        factors = build_factors(
            success_rate=success,
            behaved_rate=behaved,
            invalidation_hit_rate=invalidation,
            avoided_rate=avoided,
            raw_quality=raw_quality,
            shrunk_quality=shrunk_quality if shrunk_quality is not None else raw_quality,
            sample_size=sample_size,
            min_sample=min_sample,
        )

    verdict = decide_verdict(
        trust_tier=trust_tier,
        shrunk_quality=shrunk_quality,
        invalidation_rate=invalidation,
        avoided_rate=avoided,
    )
    warnings = build_warnings(
        condition=condition,
        sample_size=sample_size,
        min_sample=min_sample,
        trust_tier=trust_tier,
        invalidation_hit_rate=invalidation,
        avoided_rate=avoided,
        success_rate=success_rate,
        missed_entry_rate=missed_entry_rate,
        calibration=calibration,
    )
    rationale = build_rationale(
        verdict=verdict,
        condition=condition,
        sample_size=sample_size,
        min_sample=min_sample,
        invalidation_rate=invalidation,
        avoided_rate=avoided,
        success_rate=success_rate,
    )
    return DetectorScore(
        trust_tier=trust_tier,
        verdict=verdict,
        raw_quality=raw_quality,
        shrunk_quality=shrunk_quality,
        factors=factors,
        warnings=warnings,
        rationale=rationale,
    )
