"""In-memory CandidateAlertIntent store.

This is application-layer identity, not a second Telegram persistence model.
Delivery durability stays on TelegramSecurityStore outbox records.
"""

from __future__ import annotations

from threading import RLock
from typing import Protocol
from uuid import UUID

from app.candidate_alerts.contracts import CandidateAlertIntent, RiskReductionIntent
from app.candidate_alerts.errors import ConflictingCandidateAlertError


class CandidateAlertStore(Protocol):
    def get_by_identity_hash(self, identity_hash: str) -> CandidateAlertIntent | None: ...

    def get_by_intent_id(self, intent_id: UUID) -> CandidateAlertIntent | None: ...

    def get_for_payload(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        account_id: UUID,
        candidate_id: UUID,
        telegram_revision_id: UUID,
        candidate_content_hash: str,
    ) -> CandidateAlertIntent | None: ...

    def get_or_insert(self, intent: CandidateAlertIntent) -> CandidateAlertIntent: ...

    def save_risk_reduction_intent(self, row: RiskReductionIntent) -> RiskReductionIntent: ...

    def get_risk_reduction_intent(self, intent_id: UUID) -> RiskReductionIntent | None: ...


def _payload_key(
    *,
    organization_id: UUID,
    user_id: UUID,
    account_id: UUID,
    candidate_id: UUID,
    telegram_revision_id: UUID,
    candidate_content_hash: str,
) -> tuple[UUID, UUID, UUID, UUID, UUID, str]:
    return (
        organization_id,
        user_id,
        account_id,
        candidate_id,
        telegram_revision_id,
        candidate_content_hash,
    )


class InMemoryCandidateAlertStore:
    """Thread-safe get-or-insert for deterministic alert identity."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_hash: dict[str, UUID] = {}
        self._by_id: dict[UUID, CandidateAlertIntent] = {}
        self._by_payload: dict[tuple[UUID, UUID, UUID, UUID, UUID, str], UUID] = {}
        self._risk: dict[UUID, RiskReductionIntent] = {}

    def get_by_identity_hash(self, identity_hash: str) -> CandidateAlertIntent | None:
        with self._lock:
            intent_id = self._by_hash.get(identity_hash)
            if intent_id is None:
                return None
            return self._by_id[intent_id]

    def get_by_intent_id(self, intent_id: UUID) -> CandidateAlertIntent | None:
        with self._lock:
            return self._by_id.get(intent_id)

    def get_for_payload(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        account_id: UUID,
        candidate_id: UUID,
        telegram_revision_id: UUID,
        candidate_content_hash: str,
    ) -> CandidateAlertIntent | None:
        key = _payload_key(
            organization_id=organization_id,
            user_id=user_id,
            account_id=account_id,
            candidate_id=candidate_id,
            telegram_revision_id=telegram_revision_id,
            candidate_content_hash=candidate_content_hash,
        )
        with self._lock:
            intent_id = self._by_payload.get(key)
            if intent_id is None:
                return None
            return self._by_id[intent_id]

    def get_or_insert(self, intent: CandidateAlertIntent) -> CandidateAlertIntent:
        with self._lock:
            existing_id = self._by_hash.get(intent.identity_hash)
            if existing_id is not None:
                existing = self._by_id[existing_id]
                if existing.content_fingerprint != intent.content_fingerprint:
                    raise ConflictingCandidateAlertError(
                        "Candidate alert identity is bound to different structured content."
                    )
                if existing.intent_id != intent.intent_id:
                    raise ConflictingCandidateAlertError(
                        "Candidate alert identity hash is bound to a different intent id."
                    )
                return existing
            occupied = self._by_id.get(intent.intent_id)
            if occupied is not None:
                raise ConflictingCandidateAlertError(
                    "Candidate alert intent id is already bound to a different identity."
                )
            self._by_id[intent.intent_id] = intent
            self._by_hash[intent.identity_hash] = intent.intent_id
            self._by_payload[
                _payload_key(
                    organization_id=intent.organization_id,
                    user_id=intent.user_id,
                    account_id=intent.account_id,
                    candidate_id=intent.candidate_id,
                    telegram_revision_id=intent.telegram_revision_id,
                    candidate_content_hash=intent.candidate_content_hash,
                )
            ] = intent.intent_id
            return intent

    def save_risk_reduction_intent(self, row: RiskReductionIntent) -> RiskReductionIntent:
        with self._lock:
            existing = self._risk.get(row.intent_id)
            if existing is not None:
                same_snapshot = (
                    existing.candidate_id == row.candidate_id
                    and existing.candidate_content_hash == row.candidate_content_hash
                    and existing.candidate_revision == row.candidate_revision
                    and existing.alert_intent_id == row.alert_intent_id
                )
                if not same_snapshot:
                    raise ConflictingCandidateAlertError(
                        "REDUCE_RISK intent id is bound to a different candidate snapshot."
                    )
                return existing
            self._risk[row.intent_id] = row
            return row

    def get_risk_reduction_intent(self, intent_id: UUID) -> RiskReductionIntent | None:
        with self._lock:
            return self._risk.get(intent_id)
