"""Render learning evidence for later RAG ingest. Does not call RagService."""

from __future__ import annotations

from app.learning_attribution.contracts import (
    NARRATIVE_NOT_FACT_BANNER,
    AttributionRecord,
)


def render_learning_evidence_text(record: AttributionRecord) -> str:
    """Structured facts first. Narrative is labeled and cannot stand in for facts."""
    facts = record.facts
    outcome = facts.outcome
    lines = [
        "[LEARNING_EVIDENCE — derived from canonical journal lifecycle; not market truth]",
        f"Attribution ID: {facts.attribution_id}",
        f"Candidate ID: {facts.candidate_id}",
        f"Assessment ID: {facts.assessment_id}",
        f"Evidence window hash: {facts.evidence_window_hash}",
        f"Setup quality: {facts.setup_quality.axis.value}",
        f"Assessment state: {facts.setup_quality.assessment_state.value}",
        f"Execution quality: {facts.execution_quality.axis.value}",
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
    if record.narrative_explanation:
        lines.append(NARRATIVE_NOT_FACT_BANNER)
        lines.append(record.narrative_explanation)
    return "\n".join(lines)
