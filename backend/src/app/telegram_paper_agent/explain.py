"""Read-only explanations copied from canonical authorities. LLM is not used."""

from __future__ import annotations

from app.candidate_alerts.content import format_candidate_alert_text
from app.candidate_alerts.contracts import CandidateAlertContent
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.candidate import Candidate
from app.signal_fusion.evidence_window import CanonicalEvidenceWindowV1
from app.telegram_paper_agent.content import guard_paper_text
from app.telegram_paper_agent.contracts import StrategyDraftView


def explain_candidate(
    *,
    candidate: Candidate,
    content: CandidateAlertContent | None,
) -> str:
    if content is not None:
        return format_candidate_alert_text(content)
    return guard_paper_text(
        "Candidate facts (read-only).\n"
        f"candidate_id: {candidate.candidate_id}\n"
        f"state: {candidate.state.value}\n"
        f"instrument: {candidate.evidence_instrument}\n"
        f"direction: {candidate.direction.value}\n"
        f"content_hash: {candidate.content_hash}\n"
        "Telegram did not mint this Candidate."
    )


def explain_evidence(*, window: CanonicalEvidenceWindowV1, assessment: SetupAssessment) -> str:
    return guard_paper_text(
        "Evidence and SetupAssessment (read-only; not overridden).\n"
        f"assessment_state: {assessment.state.value}\n"
        f"evidence_window_hash: {window.content_hash}\n"
        f"instrument: {window.evidence_instrument}\n"
        f"fusion_policy_version: {window.fusion_policy_version}\n"
        "Missing, stale, or conflicting evidence stays fail-closed."
    )


def explain_risk(*, candidate: Candidate, assessment: SetupAssessment) -> str:
    reasons = ",".join(code.value for code in assessment.reason_codes) or "none"
    return guard_paper_text(
        "Risk and setup reasons (explanation only).\n"
        f"candidate_state: {candidate.state.value}\n"
        f"assessment_state: {assessment.state.value}\n"
        f"reason_codes: {reasons}\n"
        "Telegram cannot override RiskEngine BLOCK or kill switch."
    )


def explain_strategy(*, candidate: Candidate, draft: StrategyDraftView | None) -> str:
    extra = "" if draft is None else f"\n{draft.summary}"
    compiled = "false" if draft is None else str(draft.compiled).lower()
    approved = "false" if draft is None else str(draft.approved).lower()
    return guard_paper_text(
        "Strategy context (discussion only).\n"
        f"strategy_version_id: {candidate.strategy_version_id}\n"
        f"compiled_setup_id: {candidate.setup_definition_id}\n"
        f"conversation_compiled: {compiled}\n"
        f"conversation_approved: {approved}\n"
        "A Telegram message cannot approve or compile a strategy."
        f"{extra}"
    )


def explain_market_context(*, window: CanonicalEvidenceWindowV1) -> str:
    return guard_paper_text(
        "Market context bound to canonical evidence (not a live mark invention).\n"
        f"instrument: {window.evidence_instrument}\n"
        f"evidence_window_hash: {window.content_hash}\n"
        f"trigger: {window.trigger.natural_event_id}\n"
        "Replay or stale evidence is never treated as a current live perpetual mark."
    )
