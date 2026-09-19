"""Render learning evidence for later RAG ingest. Does not call RagService."""

from __future__ import annotations

from typing import Literal

from app.learning_attribution.contracts import (
    NARRATIVE_NOT_FACT_BANNER,
    AttributionRecord,
)
from app.market_contracts.models import CanonicalModel
from app.services.journal_rag_sync_service import sanitize_journal_text


class LearningEvidenceDocument(CanonicalModel):
    """Facts-first document for analytics/RAG. Narrative is labeled and optional."""

    attribution_id: str
    organization_id: str
    candidate_id: str
    facts_hash: str
    source_uri: str
    is_market_truth: Literal[False] = False
    facts_text: str
    narrative_text: str | None = None
    combined_text: str


def render_learning_facts_text(record: AttributionRecord) -> str:
    """Deterministic facts only. Narrative is omitted so it cannot stand in for facts."""
    facts = record.facts
    outcome = facts.outcome
    lines = [
        "[LEARNING_EVIDENCE — derived from canonical journal lifecycle; not market truth]",
        f"Attribution ID: {facts.attribution_id}",
        f"Candidate ID: {facts.candidate_id}",
        f"Assessment ID: {facts.assessment_id}",
        f"Evidence window hash: {facts.evidence_window_hash}",
        f"Learning venue mode: {facts.learning_venue_mode.value}",
        f"Setup quality: {facts.setup_quality.axis.value}",
        f"Assessment state: {facts.setup_quality.assessment_state.value}",
        f"Execution quality: {facts.execution_quality.axis.value}",
        f"Risk adherence: {facts.risk_adherence.axis.value}",
        f"Trader behavior: {facts.trader_behavior.axis.value}",
        f"Decision actor: {facts.trader_behavior.actor.value}",
        f"Executed trade outcome: {outcome.eligible}",
        f"Journal trade ID: {facts.journal_trade_id}",
        f"Execution lifecycle ID: {facts.execution_lifecycle_id}",
        f"Strategy version ID: {facts.strategy_pattern.strategy_version_id}",
        f"Setup definition ID: {facts.strategy_pattern.setup_definition_id}",
        f"Facts hash: {facts.content_hash}",
    ]
    if outcome.eligible:
        lines.append(f"Result: {outcome.result.value if outcome.result else 'unknown'}")
        lines.append(f"Net PnL: {outcome.net_pnl}")
    else:
        lines.append("Result: none (REJECT/SKIP/planned events are not executed outcomes)")
    return sanitize_journal_text("\n".join(lines))


def render_learning_evidence_text(record: AttributionRecord) -> str:
    """Structured facts first. Narrative is labeled and cannot stand in for facts."""
    facts_text = render_learning_facts_text(record)
    if not record.narrative_explanation:
        return facts_text
    narrative = sanitize_journal_text(record.narrative_explanation)
    return "\n".join((facts_text, NARRATIVE_NOT_FACT_BANNER, narrative))


def learning_evidence_document(record: AttributionRecord) -> LearningEvidenceDocument:
    """Build a consumable RAG document. Does not ingest and is not market truth."""
    facts_text = render_learning_facts_text(record)
    narrative = (
        None
        if record.narrative_explanation is None
        else sanitize_journal_text(record.narrative_explanation)
    )
    return LearningEvidenceDocument(
        attribution_id=str(record.attribution_id),
        organization_id=str(record.organization_id),
        candidate_id=str(record.candidate_id),
        facts_hash=record.facts.content_hash,
        source_uri=f"learning://{record.attribution_id}",
        facts_text=facts_text,
        narrative_text=narrative,
        combined_text=render_learning_evidence_text(record),
    )
