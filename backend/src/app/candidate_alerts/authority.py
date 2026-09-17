"""Canonical Candidate is the only candidate-alert authority."""

from __future__ import annotations

from app.candidate_alerts.contracts import CandidateAlertRecipient
from app.candidate_alerts.errors import (
    CandidateAlertBindingError,
    CandidateAlertNotFoundError,
    CandidateAlertTenantError,
    LegacyCandidateAlertAuthorityError,
)
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.candidate import Candidate
from app.signal_fusion.evidence_window import CanonicalEvidenceWindowV1
from app.signal_fusion.lifecycle import CandidateLifecycleService
from app.telegram_security.contracts import BindingState, TelegramBinding
from app.telegram_security.persistence import TelegramSecurityStore

_LEGACY_TYPE_NAMES = frozenset(
    {
        "PaperValidationCandidate",
        "PaperValidationCandidateItem",
        "PaperSignal",
        "PaperSignalResult",
        "SetupDetection",
        "SetupDetectionRecord",
        "TradingViewSignal",
        "TradingViewSignalItem",
        "DownstreamPaperValidationCandidateRef",
    }
)


def require_canonical_candidate(source: object) -> Candidate:
    """Refuse legacy entities as independent alert authorities."""
    if isinstance(source, Candidate):
        return source
    name = type(source).__name__
    if name in _LEGACY_TYPE_NAMES:
        raise LegacyCandidateAlertAuthorityError(
            f"{name} is a compatibility consumer only and cannot authorize a candidate alert.",
            details={"legacy_type": name},
        )
    raise LegacyCandidateAlertAuthorityError(
        f"{name} is not canonical Candidate authority and cannot produce a candidate alert.",
        details={"legacy_type": name},
    )


def require_matching_canonical_inputs(
    *,
    candidate: Candidate,
    assessment: SetupAssessment,
    window: CanonicalEvidenceWindowV1,
) -> None:
    if assessment.organization_id != candidate.organization_id:
        raise CandidateAlertTenantError("Assessment organization does not match Candidate.")
    if assessment.assessment_id != candidate.assessment_id:
        raise CandidateAlertTenantError("SetupAssessment is not the Candidate's assessment.")
    if assessment.strategy_version_id != candidate.strategy_version_id:
        raise CandidateAlertTenantError("Assessment strategy version does not match Candidate.")
    if assessment.evidence_window_hash != candidate.evidence_window_hash:
        raise CandidateAlertTenantError("Assessment evidence window does not match Candidate.")
    if window.content_hash != candidate.evidence_window_hash:
        raise CandidateAlertTenantError("CanonicalEvidenceWindowV1 does not match Candidate.")
    if window.organization_id != candidate.organization_id:
        raise CandidateAlertTenantError("Evidence window organization does not match Candidate.")
    if window.strategy_version_id != candidate.strategy_version_id:
        raise CandidateAlertTenantError(
            "Evidence window strategy version does not match Candidate."
        )
    if window.compiled_setup_definition_id != candidate.setup_definition_id:
        raise CandidateAlertTenantError("Compiled setup id does not match Candidate.")
    if window.compiled_setup_content_hash != candidate.executable_setup.content_hash:
        raise CandidateAlertTenantError("Compiled setup hash does not match Candidate.")
    if window.fusion_policy_version != candidate.fusion_policy_version:
        raise CandidateAlertTenantError("Fusion policy version does not match Candidate.")


def require_stored_candidate(
    lifecycle: CandidateLifecycleService,
    candidate: Candidate,
) -> Candidate:
    stored = lifecycle.get_by_candidate_id(candidate.organization_id, candidate.candidate_id)
    if stored is None:
        raise CandidateAlertNotFoundError(
            "Canonical Candidate is unknown in this organization.",
            details={"candidate_id": str(candidate.candidate_id)},
        )
    if stored.content_hash != candidate.content_hash:
        raise CandidateAlertTenantError(
            "Presented Candidate content hash does not match canonical storage."
        )
    return stored


def require_recipient_matches_candidate(
    *, candidate: Candidate, recipient: CandidateAlertRecipient
) -> None:
    if recipient.organization_id != candidate.organization_id:
        raise CandidateAlertTenantError(
            "Alert recipient organization does not match canonical Candidate."
        )


def require_active_binding(
    store: TelegramSecurityStore,
    recipient: CandidateAlertRecipient,
) -> TelegramBinding:
    binding = store.get_binding(recipient.binding_id)
    if binding is None:
        raise CandidateAlertBindingError("Telegram binding was not found.")
    if binding.revoked_at is not None or binding.state is BindingState.REVOKED:
        raise CandidateAlertBindingError("Telegram binding has been revoked.")
    if binding.organization_id != recipient.organization_id:
        raise CandidateAlertTenantError("Telegram binding organization does not match recipient.")
    if binding.user_id != recipient.user_id:
        raise CandidateAlertTenantError("Telegram binding user does not match recipient.")
    if binding.bot_id != recipient.bot_id or binding.chat_id != recipient.chat_id:
        raise CandidateAlertBindingError("Telegram binding chat/bot does not match recipient.")
    return binding
