"""Pure scoring and aggregation helpers for learning analytics (Slice 84).

Deterministic, side-effect-free functions kept separate from I/O so they can be
unit-tested in isolation. No LLM authority, no external calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_MIN_SAMPLE = 5

# (name, lower_inclusive, upper_exclusive). Upper bound of the top bucket is
# padded so a confidence of exactly 1.0 is included.
CONFIDENCE_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("low", 0.0, 0.5),
    ("medium", 0.5, 0.7),
    ("high", 0.7, 0.85),
    ("very_high", 0.85, 1.0001),
)

# Discipline credit per assessment (1.0 = fully disciplined).
DISCIPLINE_POINTS: dict[str, float] = {
    "disciplined": 1.0,
    "should_have_waited": 0.5,
    "should_have_entered": 0.4,
    "should_have_avoided": 0.0,
}


@dataclass(frozen=True)
class QualityWeights:
    """Weights for the setup quality blend. Sum of positive weights is 1.0."""

    success: float = 0.5
    behaved: float = 0.3
    invalidation_avoided: float = 0.2
    avoided_penalty: float = 20.0


QUALITY_WEIGHTS = QualityWeights()

_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "if",
        "to",
        "of",
        "in",
        "on",
        "for",
        "was",
        "were",
        "is",
        "are",
        "be",
        "been",
        "it",
        "this",
        "that",
        "with",
        "at",
        "as",
        "my",
        "i",
        "me",
        "we",
        "you",
        "he",
        "she",
        "they",
        "not",
        "no",
        "too",
        "so",
        "than",
        "then",
        "there",
        "here",
        "up",
        "down",
        "out",
        "did",
        "do",
        "does",
        "had",
        "has",
        "have",
        "will",
        "would",
        "should",
        "could",
        "more",
        "less",
        "very",
        "just",
        "into",
        "from",
        "by",
        "about",
    }
)


def safe_rate(count: int, total: int) -> float | None:
    """Return count/total rounded, or None when the denominator is zero."""
    if total <= 0:
        return None
    return round(count / total, 4)


def confidence_bucket(confidence: float | None) -> str | None:
    """Map a 0-1 confidence to a bucket name, or None when unknown/out of range."""
    if confidence is None:
        return None
    for name, lower, upper in CONFIDENCE_BUCKETS:
        if lower <= confidence < upper:
            return name
    return None


def discipline_points(assessment: str) -> float:
    """Credit for a discipline assessment; unknown values score 0."""
    return DISCIPLINE_POINTS.get(assessment, 0.0)


def discipline_grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def quality_score(
    success_rate: float,
    behaved_rate: float,
    invalidation_hit_rate: float,
    avoided_rate: float,
    *,
    weights: QualityWeights = QUALITY_WEIGHTS,
) -> float:
    """Blend outcome rates into a 0-100 setup quality score.

    Higher success and expected behaviour raise quality; invalidation hits and
    'should have avoided' assessments lower it. Result is clamped to [0, 100].
    """
    raw = 100.0 * (
        weights.success * success_rate
        + weights.behaved * behaved_rate
        + weights.invalidation_avoided * (1.0 - invalidation_hit_rate)
    )
    raw -= weights.avoided_penalty * avoided_rate
    return round(max(0.0, min(100.0, raw)), 2)


def insight_confidence(sample_size: int, min_sample: int) -> str:
    """Qualitative confidence label for an insight based on its sample size."""
    if sample_size >= 3 * min_sample:
        return "high"
    if sample_size >= max(min_sample * 3 // 2, min_sample + 1):
        return "medium"
    return "low"


def correlation_sign(pairs: list[tuple[int, float]]) -> str:
    """Sign of covariance between bucket rank and success rate.

    Returns 'positive', 'negative', 'none', or 'insufficient_data' (fewer than
    two qualifying buckets).
    """
    if len(pairs) < 2:
        return "insufficient_data"
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    if cov > 1e-6:
        return "positive"
    if cov < -1e-6:
        return "negative"
    return "none"


def extract_lesson_themes(
    texts: list[str],
    *,
    top_n: int = 8,
    max_excerpt: int = 140,
) -> list[tuple[str, int, str | None]]:
    """Return the most frequent keyword themes across lesson texts.

    Each theme is (word, count, example_excerpt). Keywords shorter than three
    characters and common stopwords are ignored.
    """
    from collections import Counter

    counter: Counter[str] = Counter()
    for text in texts:
        words = {
            word
            for word in re.findall(r"[a-zA-Z][a-zA-Z'-]+", text.lower())
            if len(word) >= 3 and word not in _STOPWORDS
        }
        counter.update(words)

    themes: list[tuple[str, int, str | None]] = []
    for word, count in counter.most_common(top_n):
        example = next((t for t in texts if word in t.lower()), None)
        if example is not None and len(example) > max_excerpt:
            example = f"{example[: max_excerpt - 3]}..."
        themes.append((word, count, example))
    return themes
