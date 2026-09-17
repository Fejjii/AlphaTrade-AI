"""Phase 6 canonical Candidate -> Telegram alert foundation.

Candidate is the only alert authority. Telegram stays a test-enabled protocol
with FakeTelegramTransport. APPROVE never executes. CLOSE stays unavailable.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.analysis.types import SetupDetection
from app.candidate_alerts.authority import require_canonical_candidate
from app.candidate_alerts.contracts import (
    CANDIDATE_RESOURCE_TYPE,
    CandidateAlertActionResult,
    CandidateAlertIntent,
    CandidateAlertKind,
    CandidateAlertProjection,
    CandidateAlertRecipient,
    DeliveryChannel,
)
from app.candidate_alerts.errors import (
    CandidateAlertTenantError,
    LegacyCandidateAlertAuthorityError,
)
from app.candidate_alerts.gateway import CandidateAlertGateway
from app.candidate_alerts.identity import build_candidate_alert_identity
from app.core.config import Settings
from app.core.deployment_safety import deployment_posture
from app.signal_fusion.adapters import DownstreamPaperValidationCandidateRef
from app.signal_fusion.enums import CandidateReasonCode, CandidateState
from app.telegram_security.actions import (
    APPROVE_EXECUTES,
    CLOSE_AVAILABLE,
    TELEGRAM_EXECUTION_ENTRY_PATHS,
    TelegramRemoteAction,
    parse_remote_action,
)
from app.telegram_security.contracts import ActionReceiptState, TelegramInboundUpdate
from app.telegram_security.errors import (
    TelegramInteractionDisabledError,
    TelegramSecurityError,
    TelegramSecurityReason,
)
from tests.support.candidate_alerts import (
    ACCOUNT_ID,
    BOT,
    CHAT,
    ORG_ID,
    USER_ID,
    AlertWorld,
    enabled_alert_world,
)
from tests.support.phase5_market import EVALUATED_AT
from tests.support.phase6_fusion import (
    make_assessment,
    make_creation_command,
    make_evidence_window,
)
from tests.support.telegram_security import (
    OTHER_ACCOUNT,
    OTHER_CHAT,
    OTHER_ORG,
    OTHER_TG_USER,
    OTHER_USER,
    callback_identity,
    enroll,
    inbound_callback,
    message_identity,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src/app/candidate_alerts"
FORBIDDEN_SNIPPETS = (
    "app.services.execution",
    "ExecutionService",
    "execute_paper_plan",
    "place_paper_order",
    "app.db.models",
    "alembic",
    "blofin",
    "VenueSubmit",
)
SIGNAL_FUSION_ROOT = Path(__file__).resolve().parents[1] / "src/app/signal_fusion"
TELEGRAM_ROOT = Path(__file__).resolve().parents[1] / "src/app/telegram_security"
OTHER_ORG_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-aaaaaaaaaaaa")


class PaperValidationCandidate:
    """Stand-in legacy type name for authority tests."""


class PaperSignal:
    """Stand-in legacy type name for authority tests."""


class TradingViewSignal:
    """Stand-in legacy type name for authority tests."""


def _project(world: AlertWorld) -> CandidateAlertProjection:
    return world.gateway.project_canonical_candidate(
        candidate=world.candidate,
        assessment=world.assessment,
        window=world.window,
        recipient=world.recipient,
    )


def _handle(
    world: AlertWorld,
    action: TelegramRemoteAction,
    *,
    update_id: int,
    callback_query_id: str,
    intent: CandidateAlertIntent | None = None,
) -> CandidateAlertActionResult:
    bound = intent if intent is not None else _project(world).intent
    issued = world.gateway.issue_action_nonce(
        binding_id=world.binding_id, intent=bound, action=action
    )
    payload = world.gateway.action_payload(bound, action)
    return world.gateway.handle_callback(
        identity=callback_identity(update_id=update_id, callback_query_id=callback_query_id),
        nonce_token=issued.token,
        presented_payload=payload,
        inbound=inbound_callback(),
    )


def test_package_does_not_import_execution_or_orm() -> None:
    for path in PACKAGE_ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for snippet in FORBIDDEN_SNIPPETS:
            assert snippet not in text, f"{path.name} contains {snippet}"


def test_signal_fusion_does_not_import_telegram() -> None:
    for path in SIGNAL_FUSION_ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "telegram_security" not in text
        assert "candidate_alerts" not in text


def test_telegram_security_does_not_import_candidate_alerts() -> None:
    for path in TELEGRAM_ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "candidate_alerts" not in text
        assert "signal_fusion" not in text


def test_telegram_and_trading_remain_disabled() -> None:
    settings = Settings()
    assert settings.telegram_interaction_enabled is False
    assert settings.telegram_alerts_enabled is False
    assert settings.automatic_telegram_delivery_enabled is False
    assert settings.real_trading_enabled is False
    assert settings.execution_mode.value == "paper"
    posture = deployment_posture(settings)
    assert posture["telegram_interaction_enabled"] is False
    gateway = CandidateAlertGateway.in_memory()
    assert gateway.protocol.enabled is False
    with pytest.raises(TelegramInteractionDisabledError):
        gateway.protocol.start_enrollment(organization_id=ORG_ID, user_id=USER_ID, bot_id=BOT)


def test_execute_paper_plan_is_outside_telegram_vocabulary() -> None:
    assert not hasattr(TelegramRemoteAction, "EXECUTE_PAPER_PLAN")
    assert TELEGRAM_EXECUTION_ENTRY_PATHS == ()
    with pytest.raises(TelegramSecurityError) as exc:
        parse_remote_action("EXECUTE_PAPER_PLAN")
    assert exc.value.reason is TelegramSecurityReason.UNKNOWN_ACTION


def test_close_is_unavailable() -> None:
    assert CLOSE_AVAILABLE is False
    world = enabled_alert_world()
    projection = _project(world)
    with pytest.raises(TelegramSecurityError) as exc:
        world.gateway.issue_action_nonce(
            binding_id=world.binding_id,
            intent=projection.intent,
            action=TelegramRemoteAction.CLOSE,
        )
    assert exc.value.reason is TelegramSecurityReason.CLOSE_UNAVAILABLE


def test_legacy_entities_cannot_authorize_alerts() -> None:
    world = enabled_alert_world()
    forbidden: tuple[object, ...] = (
        PaperValidationCandidate(),
        PaperSignal(),
        TradingViewSignal(),
        SetupDetection(name="liquidity_sweep", detected=True, direction="short", reason="legacy"),
        DownstreamPaperValidationCandidateRef(
            paper_validation_candidate_id=uuid4(),
            canonical_candidate_id=world.candidate.candidate_id,
        ),
    )
    for source in forbidden:
        with pytest.raises(LegacyCandidateAlertAuthorityError):
            require_canonical_candidate(source)
        with pytest.raises(LegacyCandidateAlertAuthorityError):
            world.gateway.project_canonical_candidate(
                candidate=source,
                assessment=world.assessment,
                window=world.window,
                recipient=world.recipient,
            )


def test_one_candidate_produces_one_alert_intent() -> None:
    world = enabled_alert_world()
    first = _project(world)
    second_create = world.lifecycle.create_from_confirmed_setup(
        make_creation_command(window=world.window, assessment=world.assessment)
    )
    assert second_create.candidate_id == world.candidate.candidate_id
    second = world.gateway.project_canonical_candidate(
        candidate=second_create,
        assessment=world.assessment,
        window=world.window,
        recipient=world.recipient,
    )
    assert first.intent.intent_id == second.intent.intent_id
    assert first.intent.identity_hash == second.intent.identity_hash
    assert first.outbox.outbox_id == second.outbox.outbox_id
    assert second.converged is True
    assert world.transport.send_count == 0
    assert world.transport.attempts == []
    assert first.intent.alert_kind is CandidateAlertKind.CANDIDATE_ACTIVE
    assert first.intent.delivery_channel is DeliveryChannel.TELEGRAM
    assert first.intent.content.candidate_id == world.candidate.candidate_id
    assert first.intent.content.candidate_revision == 1
    assert "Bearish Liquidity Sweep" in first.intent.content.setup_name
    assert "profit" not in first.outbox.text.lower()
    assert "guaranteed" not in first.outbox.text.lower()
    assert first.intent.content.invalidation.bound_to_expiry is True


def test_duplicate_candidate_event_converges() -> None:
    world = enabled_alert_world()
    left_id, left_hash = build_candidate_alert_identity(
        organization_id=ORG_ID,
        user_id=USER_ID,
        account_id=ACCOUNT_ID,
        candidate_id=world.candidate.candidate_id,
        candidate_content_hash=world.candidate.content_hash,
        strategy_version_id=world.candidate.strategy_version_id,
        compiled_setup_definition_id=world.candidate.setup_definition_id,
        compiled_setup_content_hash=world.candidate.executable_setup.content_hash,
        fusion_policy_version=world.candidate.fusion_policy_version,
        evidence_window_hash=world.candidate.evidence_window_hash,
        candidate_lifecycle_revision=world.candidate.transition_version,
    )
    right_id, right_hash = build_candidate_alert_identity(
        organization_id=ORG_ID,
        user_id=USER_ID,
        account_id=ACCOUNT_ID,
        candidate_id=world.candidate.candidate_id,
        candidate_content_hash=world.candidate.content_hash,
        strategy_version_id=world.candidate.strategy_version_id,
        compiled_setup_definition_id=world.candidate.setup_definition_id,
        compiled_setup_content_hash=world.candidate.executable_setup.content_hash,
        fusion_policy_version=world.candidate.fusion_policy_version,
        evidence_window_hash=world.candidate.evidence_window_hash,
        candidate_lifecycle_revision=world.candidate.transition_version,
    )
    assert left_id == right_id
    assert left_hash == right_hash
    first = _project(world)
    second = _project(world)
    assert first.intent.intent_id == second.intent.intent_id == left_id
    assert first.outbox.idempotency_key == second.outbox.idempotency_key
    assert first.outbox.outbox_id == second.outbox.outbox_id


def test_changed_candidate_revision_produces_distinct_identity() -> None:
    world = enabled_alert_world()
    first = _project(world)
    rejected = world.lifecycle.transition(
        organization_id=ORG_ID,
        candidate_id=world.candidate.candidate_id,
        new_state=CandidateState.REJECTED,
        reason_codes=(CandidateReasonCode.REJECTED,),
        idempotency_key="manual-reject-revision",
        correlation_id=uuid4(),
    )
    assert rejected.transition_version == 2
    assert rejected.content_hash != world.candidate.content_hash
    second = world.gateway.project_canonical_candidate(
        candidate=rejected,
        assessment=world.assessment,
        window=world.window,
        recipient=world.recipient,
    )
    assert second.intent.intent_id != first.intent.intent_id
    assert second.intent.identity_hash != first.intent.identity_hash
    assert second.intent.candidate_lifecycle_revision == 2
    assert second.outbox.outbox_id != first.outbox.outbox_id
    assert second.converged is False


def test_tenant_isolation_rejects_foreign_organization() -> None:
    world = enabled_alert_world()
    foreign_window = make_evidence_window(organization_id=OTHER_ORG_ID)
    foreign_assessment = make_assessment(foreign_window, organization_id=OTHER_ORG_ID)
    foreign = world.lifecycle.create_from_confirmed_setup(
        make_creation_command(
            window=foreign_window,
            assessment=foreign_assessment,
            idempotency_key="foreign-candidate",
        )
    )
    with pytest.raises(CandidateAlertTenantError):
        world.gateway.project_canonical_candidate(
            candidate=foreign,
            assessment=foreign_assessment,
            window=foreign_window,
            recipient=world.recipient,
        )
    assert world.lifecycle.get_by_candidate_id(ORG_ID, foreign.candidate_id) is None
    assert world.lifecycle.get_by_candidate_id(OTHER_ORG_ID, world.candidate.candidate_id) is None


def test_account_and_user_identity_isolation() -> None:
    world = enabled_alert_world()
    first = _project(world)
    other_account = world.recipient.model_copy(update={"account_id": OTHER_ACCOUNT})
    second = world.gateway.project_canonical_candidate(
        candidate=world.candidate,
        assessment=world.assessment,
        window=world.window,
        recipient=other_account,
    )
    assert second.intent.intent_id != first.intent.intent_id
    assert second.intent.account_id == OTHER_ACCOUNT
    _, other_binding = enroll(
        world.protocol,
        organization_id=ORG_ID,
        user_id=OTHER_USER,
        identity=message_identity(
            update_id=2,
            telegram_user_id=OTHER_TG_USER,
            chat_id=OTHER_CHAT,
            message_id="msg-2",
        ),
    )
    other_user = CandidateAlertRecipient(
        organization_id=ORG_ID,
        user_id=OTHER_USER,
        account_id=ACCOUNT_ID,
        binding_id=other_binding,
        bot_id=BOT,
        chat_id=OTHER_CHAT,
    )
    third = world.gateway.project_canonical_candidate(
        candidate=world.candidate,
        assessment=world.assessment,
        window=world.window,
        recipient=other_user,
    )
    assert third.intent.intent_id != first.intent.intent_id
    assert third.intent.user_id == OTHER_USER


def test_candidate_content_hash_is_bound_on_callback() -> None:
    world = enabled_alert_world()
    projection = _project(world)
    issued = world.gateway.issue_action_nonce(
        binding_id=world.binding_id,
        intent=projection.intent,
        action=TelegramRemoteAction.APPROVE,
    )
    mutated = world.gateway.action_payload(projection.intent, TelegramRemoteAction.APPROVE)
    mutated = mutated.model_copy(update={"content_hash": "b" * 64})
    outcome = world.gateway.handle_callback(
        identity=callback_identity(update_id=40, callback_query_id="cb-hash"),
        nonce_token=issued.token,
        presented_payload=mutated,
        inbound=inbound_callback(),
    )
    assert outcome.telegram_outcome.receipt.state is ActionReceiptState.REJECTED
    assert outcome.telegram_outcome.reason_code == TelegramSecurityReason.PAYLOAD_MISMATCH.value
    assert outcome.candidate_mutated is False
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.ACTIVE
    assert stored.content_hash == world.candidate.content_hash


def test_approve_never_executes() -> None:
    world = enabled_alert_world()
    result = _handle(
        world, TelegramRemoteAction.APPROVE, update_id=50, callback_query_id="cb-approve"
    )
    intent = result.authorization_intent
    assert intent is not None
    assert intent.executes is False
    assert intent.execution_attempted is False
    assert intent.execution_entry_path is None
    assert result.executed is False
    assert result.execution_attempted is False
    assert result.paper_plan_invoked is False
    assert result.execution_command_id is None
    assert result.candidate_mutated is False
    assert result.candidate_state is CandidateState.ACTIVE
    assert APPROVE_EXECUTES is False
    assert world.gateway.execution_attempt_count == 0
    assert world.protocol.execution_attempt_count == 0
    assert world.lifecycle.transition_history(ORG_ID, world.candidate.candidate_id) == ()
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.ACTIVE
    payload_resource = result.intent
    assert payload_resource is not None
    assert payload_resource.candidate_id == world.candidate.candidate_id


def test_reject_maps_to_canonical_candidate_transition() -> None:
    world = enabled_alert_world()
    result = _handle(
        world, TelegramRemoteAction.REJECT, update_id=51, callback_query_id="cb-reject"
    )
    assert result.candidate_mutated is True
    assert result.candidate_state is CandidateState.REJECTED
    assert result.executed is False
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.REJECTED
    history = world.lifecycle.transition_history(ORG_ID, world.candidate.candidate_id)
    assert len(history) == 1
    assert history[0].new_state is CandidateState.REJECTED
    assert CandidateReasonCode.REJECTED in history[0].reason_codes


def test_skip_maps_to_canonical_candidate_transition() -> None:
    world = enabled_alert_world()
    result = _handle(world, TelegramRemoteAction.SKIP, update_id=52, callback_query_id="cb-skip")
    assert result.candidate_state is CandidateState.SKIPPED
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.SKIPPED
    history = world.lifecycle.transition_history(ORG_ID, world.candidate.candidate_id)
    assert history[0].new_state is CandidateState.SKIPPED


def test_reduce_risk_does_not_mutate_candidate() -> None:
    world = enabled_alert_world()
    before = world.candidate.content_hash
    result = _handle(
        world,
        TelegramRemoteAction.REDUCE_RISK,
        update_id=53,
        callback_query_id="cb-reduce",
    )
    assert result.candidate_mutated is False
    assert result.candidate_state is CandidateState.ACTIVE
    risk = result.risk_reduction_intent
    assert risk is not None
    assert risk.mutates_candidate is False
    assert risk.creates_plan_revision is False
    assert risk.executes is False
    assert risk.future_plan_revision_required is True
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.content_hash == before
    assert stored.state is CandidateState.ACTIVE
    assert world.lifecycle.transition_history(ORG_ID, world.candidate.candidate_id) == ()


def test_explain_show_chart_and_status_are_read_only() -> None:
    world = enabled_alert_world()
    projection = _project(world)
    explain = _handle(
        world,
        TelegramRemoteAction.EXPLAIN,
        update_id=54,
        callback_query_id="cb-explain",
        intent=projection.intent,
    )
    chart = _handle(
        world,
        TelegramRemoteAction.SHOW_CHART,
        update_id=55,
        callback_query_id="cb-chart",
        intent=projection.intent,
    )
    status = _handle(
        world,
        TelegramRemoteAction.STATUS,
        update_id=56,
        callback_query_id="cb-status",
        intent=projection.intent,
    )
    for result in (explain, chart, status):
        assert result.candidate_mutated is False
        assert result.executed is False
        assert result.candidate_state is CandidateState.ACTIVE
        assert result.read_only_view is not None
        assert result.read_only_view.mutates_candidate is False
    assert explain.read_only_view is not None
    assert explain.read_only_view.rule_results
    assert chart.read_only_view is not None
    assert chart.read_only_view.trigger_context is not None
    assert status.read_only_view is not None
    assert status.read_only_view.trigger_context is None
    assert status.read_only_view.rule_results == ()
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.content_hash == world.candidate.content_hash
    assert world.lifecycle.transition_history(ORG_ID, world.candidate.candidate_id) == ()


def test_exact_callback_replay_converges() -> None:
    world = enabled_alert_world()
    projection = _project(world)
    issued = world.gateway.issue_action_nonce(
        binding_id=world.binding_id,
        intent=projection.intent,
        action=TelegramRemoteAction.REJECT,
    )
    payload = world.gateway.action_payload(projection.intent, TelegramRemoteAction.REJECT)
    identity = callback_identity(update_id=70, callback_query_id="cb-replay")
    first = world.gateway.handle_callback(
        identity=identity,
        nonce_token=issued.token,
        presented_payload=payload,
        inbound=inbound_callback(),
    )
    second = world.gateway.handle_callback(
        identity=identity,
        nonce_token=issued.token,
        presented_payload=payload,
        inbound=inbound_callback(),
    )
    assert second.telegram_outcome.replayed is True
    assert second.telegram_outcome.receipt.receipt_id == first.telegram_outcome.receipt.receipt_id
    history = world.lifecycle.transition_history(ORG_ID, world.candidate.candidate_id)
    assert len(history) == 1
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.REJECTED


def test_conflicting_replay_fails_closed() -> None:
    world = enabled_alert_world()
    projection = _project(world)
    issued = world.gateway.issue_action_nonce(
        binding_id=world.binding_id,
        intent=projection.intent,
        action=TelegramRemoteAction.STATUS,
    )
    payload = world.gateway.action_payload(projection.intent, TelegramRemoteAction.STATUS)
    identity = callback_identity(update_id=71, callback_query_id="cb-conflict")
    first = world.gateway.handle_callback(
        identity=identity,
        nonce_token=issued.token,
        presented_payload=payload,
        inbound=inbound_callback(),
    )
    assert first.telegram_outcome.receipt.state is ActionReceiptState.APPLIED
    mutated = payload.model_copy(update={"content_hash": "c" * 64})
    with pytest.raises(TelegramSecurityError) as exc:
        world.gateway.handle_callback(
            identity=identity,
            nonce_token=issued.token,
            presented_payload=mutated,
            inbound=inbound_callback(),
        )
    assert exc.value.reason is TelegramSecurityReason.REPLAY_CONFLICT
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.ACTIVE
    assert stored.content_hash == world.candidate.content_hash


def test_outbox_idempotency_preserved() -> None:
    world = enabled_alert_world()
    first = _project(world)
    second = _project(world)
    assert first.outbox.idempotency_key == second.outbox.idempotency_key
    assert first.outbox.outbox_id == second.outbox.outbox_id
    assert first.outbox.text == second.outbox.text
    looked_up = world.protocol.store.get_outbox_by_idempotency(
        organization_id=ORG_ID, idempotency_key=first.outbox.idempotency_key
    )
    assert looked_up is not None
    assert looked_up.outbox_id == first.outbox.outbox_id
    assert world.transport.send_count == 0


def test_oversized_inbound_rejected_before_candidate_mutation() -> None:
    world = enabled_alert_world()
    projection = _project(world)
    issued = world.gateway.issue_action_nonce(
        binding_id=world.binding_id,
        intent=projection.intent,
        action=TelegramRemoteAction.REJECT,
    )
    with pytest.raises(TelegramSecurityError) as exc:
        world.gateway.handle_callback(
            identity=callback_identity(update_id=80, callback_query_id="cb-big"),
            nonce_token=issued.token,
            presented_payload=world.gateway.action_payload(
                projection.intent, TelegramRemoteAction.REJECT
            ),
            inbound=TelegramInboundUpdate(update_type="callback_query", body_size=64_001),
        )
    assert exc.value.reason is TelegramSecurityReason.UPDATE_TOO_LARGE
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.ACTIVE


def test_cross_organization_callback_rejected() -> None:
    world = enabled_alert_world()
    projection = _project(world)
    issued = world.gateway.issue_action_nonce(
        binding_id=world.binding_id,
        intent=projection.intent,
        action=TelegramRemoteAction.REJECT,
    )
    payload = world.gateway.action_payload(projection.intent, TelegramRemoteAction.REJECT)
    foreign = payload.model_copy(update={"organization_id": OTHER_ORG})
    outcome = world.gateway.handle_callback(
        identity=callback_identity(update_id=81, callback_query_id="cb-org"),
        nonce_token=issued.token,
        presented_payload=foreign,
        inbound=inbound_callback(),
    )
    assert outcome.telegram_outcome.reason_code == TelegramSecurityReason.CROSS_ORGANIZATION.value
    stored = world.lifecycle.get_by_candidate_id(ORG_ID, world.candidate.candidate_id)
    assert stored is not None
    assert stored.state is CandidateState.ACTIVE


def test_no_telegram_webhook_route_is_registered() -> None:
    from app.main import create_app

    app = create_app()
    paths = [getattr(route, "path", "") for route in app.routes]
    assert not any("telegram" in path and "webhook" in path for path in paths)


def test_resource_type_is_candidate() -> None:
    world = enabled_alert_world()
    projection = _project(world)
    payload = world.gateway.action_payload(projection.intent, TelegramRemoteAction.STATUS)
    assert payload.resource_type == CANDIDATE_RESOURCE_TYPE
    assert payload.resource_id == world.candidate.candidate_id
    assert payload.content_hash == world.candidate.content_hash


def test_disabled_gateway_cannot_enqueue() -> None:
    gateway = CandidateAlertGateway.in_memory(enabled=False, now=EVALUATED_AT)
    assert gateway.protocol.enabled is False
    with pytest.raises(TelegramInteractionDisabledError):
        gateway.protocol.enqueue_outbound(
            organization_id=ORG_ID,
            user_id=USER_ID,
            bot_id=BOT,
            chat_id=CHAT,
            text="candidate-alert-disabled",
            idempotency_key="disabled-test-key-01",
        )
