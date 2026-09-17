"""Typed application boundary: canonical Candidate alerts over Telegram security.

CandidateLifecycleService remains candidate authority. TelegramSecurityProtocol
remains enrollment/nonce/receipt/outbox authority. This gateway composes them
without activating webhooks, network delivery, or execution.

APPROVE records authorization intent only. REJECT/SKIP map to canonical
Candidate transitions. REDUCE_RISK does not mutate Candidate. EXPLAIN,
SHOW_CHART, and STATUS are read-only. CLOSE stays unavailable.
EXECUTE_PAPER_PLAN is not implemented.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.candidate_alerts.authority import (
    require_active_binding,
    require_canonical_candidate,
    require_matching_canonical_inputs,
    require_recipient_matches_candidate,
    require_stored_candidate,
)
from app.candidate_alerts.content import build_candidate_alert_content, format_candidate_alert_text
from app.candidate_alerts.contracts import (
    CANDIDATE_ALERT_OUTBOX_PREFIX,
    CANDIDATE_RESOURCE_TYPE,
    CandidateAlertActionResult,
    CandidateAlertIntent,
    CandidateAlertKind,
    CandidateAlertProjection,
    CandidateAlertRecipient,
    CandidateReadView,
    DeliveryChannel,
    RiskReductionIntent,
)
from app.candidate_alerts.errors import CandidateAlertNotFoundError
from app.candidate_alerts.identity import (
    build_candidate_alert_identity,
    candidate_telegram_revision_id,
    risk_reduction_intent_id,
)
from app.candidate_alerts.memory import CandidateAlertStore, InMemoryCandidateAlertStore
from app.services.canonical_serialization import canonical_sha256
from app.signal_fusion.assessment import SetupAssessment
from app.signal_fusion.candidate import Candidate
from app.signal_fusion.enums import CandidateReasonCode, CandidateState
from app.signal_fusion.evidence_window import CanonicalEvidenceWindowV1
from app.signal_fusion.lifecycle import CandidateLifecycleService, in_memory_candidate_lifecycle
from app.telegram_security.actions import (
    READ_ONLY_TELEGRAM_ACTIONS,
    TelegramRemoteAction,
    effect_kind_for,
    parse_remote_action,
)
from app.telegram_security.clock import Clock, FrozenClock
from app.telegram_security.contracts import (
    ActionOutcome,
    ActionPayload,
    ActionReceiptState,
    CallbackIdentity,
    IssueNonceResult,
    TelegramInboundUpdate,
)
from app.telegram_security.errors import TelegramSecurityError, TelegramSecurityReason
from app.telegram_security.protocol import TelegramSecurityProtocol

_READ_ONLY = READ_ONLY_TELEGRAM_ACTIONS


class CandidateAlertGateway:
    """Canonical Candidate -> deterministic alert intent -> Telegram outbox -> actions."""

    def __init__(
        self,
        *,
        lifecycle: CandidateLifecycleService,
        protocol: TelegramSecurityProtocol,
        clock: Clock,
        store: CandidateAlertStore | None = None,
    ) -> None:
        self._lifecycle = lifecycle
        self._protocol = protocol
        self._clock = clock
        self._store = store or InMemoryCandidateAlertStore()
        self.execution_attempt_count = 0

    @classmethod
    def in_memory(
        cls,
        *,
        enabled: bool = False,
        now: datetime | None = None,
        protocol: TelegramSecurityProtocol | None = None,
        lifecycle: CandidateLifecycleService | None = None,
    ) -> CandidateAlertGateway:
        clock = FrozenClock(now) if now is not None else FrozenClock()
        resolved_protocol = protocol or TelegramSecurityProtocol.in_memory(
            enabled=enabled, clock=clock
        )
        resolved_lifecycle = lifecycle or in_memory_candidate_lifecycle(now=clock.now())
        return cls(lifecycle=resolved_lifecycle, protocol=resolved_protocol, clock=clock)

    @property
    def protocol(self) -> TelegramSecurityProtocol:
        return self._protocol

    @property
    def lifecycle(self) -> CandidateLifecycleService:
        return self._lifecycle

    @property
    def store(self) -> CandidateAlertStore:
        return self._store

    def project_canonical_candidate(
        self,
        *,
        candidate: object,
        assessment: SetupAssessment,
        window: CanonicalEvidenceWindowV1,
        recipient: CandidateAlertRecipient,
        alert_kind: CandidateAlertKind = CandidateAlertKind.CANDIDATE_ACTIVE,
    ) -> CandidateAlertProjection:
        """Insert or converge one CandidateAlertIntent and enqueue the Telegram outbox row."""
        canonical = require_canonical_candidate(candidate)
        stored = require_stored_candidate(self._lifecycle, canonical)
        require_matching_canonical_inputs(candidate=stored, assessment=assessment, window=window)
        require_recipient_matches_candidate(candidate=stored, recipient=recipient)
        require_active_binding(self._protocol.store, recipient)
        intent = self._build_intent(
            candidate=stored,
            assessment=assessment,
            window=window,
            recipient=recipient,
            alert_kind=alert_kind,
        )
        prior_intent = self._store.get_by_identity_hash(intent.identity_hash)
        persisted = self._store.get_or_insert(intent)
        existing_before = self._protocol.store.get_outbox_by_idempotency(
            organization_id=persisted.organization_id,
            idempotency_key=_outbox_key(persisted.identity_hash),
        )
        outbox = self._protocol.enqueue_outbound(
            organization_id=persisted.organization_id,
            user_id=persisted.user_id,
            bot_id=recipient.bot_id,
            chat_id=recipient.chat_id,
            text=format_candidate_alert_text(persisted.content),
            idempotency_key=_outbox_key(persisted.identity_hash),
            binding_id=recipient.binding_id,
        )
        return CandidateAlertProjection(
            intent=persisted,
            outbox=outbox,
            converged=prior_intent is not None or existing_before is not None,
        )

    def issue_action_nonce(
        self,
        *,
        binding_id: UUID,
        intent: CandidateAlertIntent,
        action: TelegramRemoteAction | str,
    ) -> IssueNonceResult:
        resolved = _parse_action(action)
        return self._protocol.issue_action_nonce(
            binding_id=binding_id,
            payload=self.action_payload(intent, resolved),
        )

    def action_payload(
        self, intent: CandidateAlertIntent, action: TelegramRemoteAction
    ) -> ActionPayload:
        return ActionPayload(
            action=action,
            organization_id=intent.organization_id,
            user_id=intent.user_id,
            account_id=intent.account_id,
            resource_type=CANDIDATE_RESOURCE_TYPE,
            resource_id=intent.candidate_id,
            revision_id=intent.telegram_revision_id,
            content_hash=intent.candidate_content_hash,
        )

    def handle_callback(
        self,
        *,
        identity: CallbackIdentity,
        nonce_token: str,
        presented_payload: ActionPayload,
        inbound: TelegramInboundUpdate,
    ) -> CandidateAlertActionResult:
        """Authorize via Telegram protocol, then apply the typed candidate boundary."""
        outcome = self._protocol.receive_callback(
            identity=identity,
            nonce_token=nonce_token,
            presented_payload=presented_payload,
            inbound=inbound,
        )
        revision_id = presented_payload.revision_id
        intent = None
        if revision_id is not None:
            intent = self._store.get_for_payload(
                organization_id=presented_payload.organization_id,
                user_id=presented_payload.user_id,
                account_id=presented_payload.account_id,
                candidate_id=presented_payload.resource_id,
                telegram_revision_id=revision_id,
                candidate_content_hash=presented_payload.content_hash,
            )
        if outcome.receipt.state is not ActionReceiptState.APPLIED:
            candidate = self._lifecycle.get_by_candidate_id(
                presented_payload.organization_id, presented_payload.resource_id
            )
            return CandidateAlertActionResult(
                telegram_outcome=outcome,
                intent=intent,
                candidate_state=None if candidate is None else candidate.state,
                candidate_revision=None if candidate is None else candidate.transition_version,
                effect_kind=outcome.effect_kind,
                candidate_mutated=False,
            )
        if intent is None:
            raise CandidateAlertNotFoundError(
                "No CandidateAlertIntent is bound to this Telegram payload."
            )
        return self._apply_authorized_action(
            intent=intent, payload=presented_payload, outcome=outcome
        )

    def _apply_authorized_action(
        self,
        *,
        intent: CandidateAlertIntent,
        payload: ActionPayload,
        outcome: ActionOutcome,
    ) -> CandidateAlertActionResult:
        action = payload.action
        candidate = self._lifecycle.get_by_candidate_id(intent.organization_id, intent.candidate_id)
        if candidate is None:
            raise CandidateAlertNotFoundError(
                "Canonical Candidate is unknown in this organization."
            )
        if action is TelegramRemoteAction.APPROVE:
            return self._approve_result(intent, candidate, outcome)
        if action is TelegramRemoteAction.REJECT:
            return self._transition_result(
                intent,
                outcome,
                new_state=CandidateState.REJECTED,
                reason=CandidateReasonCode.REJECTED,
                action=action,
            )
        if action is TelegramRemoteAction.SKIP:
            return self._transition_result(
                intent,
                outcome,
                new_state=CandidateState.SKIPPED,
                reason=CandidateReasonCode.SKIPPED,
                action=action,
            )
        if action is TelegramRemoteAction.REDUCE_RISK:
            return self._reduce_risk_result(intent, candidate, outcome)
        if action in _READ_ONLY:
            return self._read_only_result(intent, candidate, outcome, action)
        raise TelegramSecurityError(
            f"Telegram action {action.value} is not allowed on a candidate alert.",
            reason=TelegramSecurityReason.ACTION_NOT_ALLOWED,
            details={"action": action.value},
        )

    def _approve_result(
        self,
        intent: CandidateAlertIntent,
        candidate: Candidate,
        outcome: ActionOutcome,
    ) -> CandidateAlertActionResult:
        return CandidateAlertActionResult(
            telegram_outcome=outcome,
            intent=intent,
            candidate_state=candidate.state,
            candidate_revision=candidate.transition_version,
            authorization_intent=outcome.authorization_intent,
            effect_kind=effect_kind_for(TelegramRemoteAction.APPROVE),
            candidate_mutated=False,
        )

    def _transition_result(
        self,
        intent: CandidateAlertIntent,
        outcome: ActionOutcome,
        *,
        new_state: CandidateState,
        reason: CandidateReasonCode,
        action: TelegramRemoteAction,
    ) -> CandidateAlertActionResult:
        previous = self._lifecycle.get_by_candidate_id(intent.organization_id, intent.candidate_id)
        updated = self._lifecycle.transition(
            organization_id=intent.organization_id,
            candidate_id=intent.candidate_id,
            new_state=new_state,
            reason_codes=(reason,),
            idempotency_key=_transition_key(action, intent.intent_id),
            correlation_id=intent.intent_id,
        )
        mutated = previous is None or previous.content_hash != updated.content_hash
        return CandidateAlertActionResult(
            telegram_outcome=outcome,
            intent=intent,
            candidate_state=updated.state,
            candidate_revision=updated.transition_version,
            effect_kind=effect_kind_for(action),
            candidate_mutated=mutated,
        )

    def _reduce_risk_result(
        self,
        intent: CandidateAlertIntent,
        candidate: Candidate,
        outcome: ActionOutcome,
    ) -> CandidateAlertActionResult:
        risk = RiskReductionIntent(
            intent_id=risk_reduction_intent_id(alert_intent_id=intent.intent_id),
            organization_id=intent.organization_id,
            user_id=intent.user_id,
            account_id=intent.account_id,
            candidate_id=intent.candidate_id,
            candidate_content_hash=intent.candidate_content_hash,
            candidate_revision=intent.candidate_lifecycle_revision,
            alert_intent_id=intent.intent_id,
            receipt_id=outcome.receipt.receipt_id,
            created_at=self._clock.now(),
        )
        stored = self._store.save_risk_reduction_intent(risk)
        return CandidateAlertActionResult(
            telegram_outcome=outcome,
            intent=intent,
            candidate_state=candidate.state,
            candidate_revision=candidate.transition_version,
            risk_reduction_intent=stored,
            effect_kind=effect_kind_for(TelegramRemoteAction.REDUCE_RISK),
            candidate_mutated=False,
        )

    def _read_only_result(
        self,
        intent: CandidateAlertIntent,
        candidate: Candidate,
        outcome: ActionOutcome,
        action: TelegramRemoteAction,
    ) -> CandidateAlertActionResult:
        content = intent.content
        view = CandidateReadView(
            action=action,
            candidate_id=candidate.candidate_id,
            candidate_revision=candidate.transition_version,
            candidate_state=candidate.state,
            setup_state=content.setup_state,
            instrument=content.instrument,
            direction=content.direction,
            expiry=candidate.valid_until,
            setup_name=content.setup_name,
            trigger_context=(
                None if action is TelegramRemoteAction.STATUS else content.trigger_context
            ),
            rule_results=content.rule_results if action is TelegramRemoteAction.EXPLAIN else (),
        )
        return CandidateAlertActionResult(
            telegram_outcome=outcome,
            intent=intent,
            candidate_state=candidate.state,
            candidate_revision=candidate.transition_version,
            read_only_view=view,
            effect_kind=effect_kind_for(action),
            candidate_mutated=False,
        )

    def _build_intent(
        self,
        *,
        candidate: Candidate,
        assessment: SetupAssessment,
        window: CanonicalEvidenceWindowV1,
        recipient: CandidateAlertRecipient,
        alert_kind: CandidateAlertKind,
    ) -> CandidateAlertIntent:
        intent_id, identity_hash = build_candidate_alert_identity(
            organization_id=recipient.organization_id,
            user_id=recipient.user_id,
            account_id=recipient.account_id,
            candidate_id=candidate.candidate_id,
            candidate_content_hash=candidate.content_hash,
            strategy_version_id=candidate.strategy_version_id,
            compiled_setup_definition_id=candidate.setup_definition_id,
            compiled_setup_content_hash=candidate.executable_setup.content_hash,
            fusion_policy_version=candidate.fusion_policy_version,
            evidence_window_hash=candidate.evidence_window_hash,
            candidate_lifecycle_revision=candidate.transition_version,
            alert_kind=alert_kind,
            delivery_channel=DeliveryChannel.TELEGRAM,
        )
        content = build_candidate_alert_content(
            candidate=candidate, assessment=assessment, window=window
        )
        return CandidateAlertIntent(
            intent_id=intent_id,
            identity_hash=identity_hash,
            organization_id=recipient.organization_id,
            user_id=recipient.user_id,
            account_id=recipient.account_id,
            candidate_id=candidate.candidate_id,
            candidate_content_hash=candidate.content_hash,
            strategy_version_id=candidate.strategy_version_id,
            compiled_setup_definition_id=candidate.setup_definition_id,
            compiled_setup_content_hash=candidate.executable_setup.content_hash,
            fusion_policy_version=candidate.fusion_policy_version,
            evidence_window_hash=candidate.evidence_window_hash,
            candidate_lifecycle_revision=candidate.transition_version,
            telegram_revision_id=candidate_telegram_revision_id(
                candidate_id=candidate.candidate_id,
                lifecycle_revision=candidate.transition_version,
            ),
            alert_kind=alert_kind,
            delivery_channel=DeliveryChannel.TELEGRAM,
            content=content,
            content_fingerprint=canonical_sha256(content),
            created_at=self._clock.now(),
        )


def _parse_action(action: TelegramRemoteAction | str) -> TelegramRemoteAction:
    if isinstance(action, TelegramRemoteAction):
        if action is TelegramRemoteAction.CLOSE:
            raise TelegramSecurityError(
                "Telegram CLOSE is unavailable.",
                reason=TelegramSecurityReason.CLOSE_UNAVAILABLE,
            )
        return action
    return parse_remote_action(action)


def _outbox_key(identity_hash: str) -> str:
    return f"{CANDIDATE_ALERT_OUTBOX_PREFIX}{identity_hash}"


def _transition_key(action: TelegramRemoteAction, intent_id: UUID) -> str:
    return f"tg-{action.value.lower()}:{intent_id}"
