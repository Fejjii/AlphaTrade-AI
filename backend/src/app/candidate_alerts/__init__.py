"""Canonical Candidate -> Telegram alert composition.

Candidate from Phase 6 is the only candidate-alert authority. Telegram
interaction remains disabled by default. APPROVE never executes.
"""

from app.candidate_alerts.contracts import (
    CANDIDATE_ALERT_SCHEMA,
    CANDIDATE_RESOURCE_TYPE,
    CandidateAlertActionResult,
    CandidateAlertContent,
    CandidateAlertIntent,
    CandidateAlertKind,
    CandidateAlertProjection,
    CandidateAlertRecipient,
    CandidateReadView,
    DeliveryChannel,
    RiskReductionIntent,
)
from app.candidate_alerts.errors import (
    CandidateAlertBindingError,
    CandidateAlertError,
    CandidateAlertNotFoundError,
    CandidateAlertTenantError,
    ConflictingCandidateAlertError,
    LegacyCandidateAlertAuthorityError,
)
from app.candidate_alerts.gateway import CandidateAlertGateway
from app.candidate_alerts.identity import (
    build_candidate_alert_identity,
    candidate_telegram_revision_id,
    hash_candidate_alert_identity,
)
from app.candidate_alerts.memory import InMemoryCandidateAlertStore
from app.telegram_security.actions import parse_remote_action

__all__ = [
    "CANDIDATE_ALERT_SCHEMA",
    "CANDIDATE_RESOURCE_TYPE",
    "CandidateAlertActionResult",
    "CandidateAlertBindingError",
    "CandidateAlertContent",
    "CandidateAlertError",
    "CandidateAlertGateway",
    "CandidateAlertIntent",
    "CandidateAlertKind",
    "CandidateAlertNotFoundError",
    "CandidateAlertProjection",
    "CandidateAlertRecipient",
    "CandidateAlertTenantError",
    "CandidateReadView",
    "ConflictingCandidateAlertError",
    "DeliveryChannel",
    "InMemoryCandidateAlertStore",
    "LegacyCandidateAlertAuthorityError",
    "RiskReductionIntent",
    "build_candidate_alert_identity",
    "candidate_telegram_revision_id",
    "hash_candidate_alert_identity",
    "parse_remote_action",
]
