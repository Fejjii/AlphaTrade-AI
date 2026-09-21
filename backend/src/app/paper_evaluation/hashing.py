"""Hash helpers for paper-evaluation facts. Narrative is never part of the digest."""

from __future__ import annotations

from app.market_contracts.hashing import with_content_hash
from app.paper_evaluation.contracts import PaperEvaluationFacts, PaperEvaluationObservation

# occurred_at is recording time, not semantic identity. generated_at is query time.
_OBSERVATION_EXCLUDE = frozenset({"narrative_explanation", "occurred_at"})
_FACTS_EXCLUDE = frozenset({"generated_at"})


def hashed_observation(observation: PaperEvaluationObservation) -> PaperEvaluationObservation:
    return with_content_hash(observation, extra_exclude=_OBSERVATION_EXCLUDE)


def hashed_facts(facts: PaperEvaluationFacts) -> PaperEvaluationFacts:
    return with_content_hash(facts, extra_exclude=_FACTS_EXCLUDE)
