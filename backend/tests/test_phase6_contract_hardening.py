"""Phase 6 contract freeze hardening: identity, assertion selection, set semantics."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.market_contracts.enums import Finality, FreshnessState
from app.market_contracts.hashing import with_content_hash
from app.market_contracts.identity import EvidenceMarketIdentity, binance_usdm_btcusdt
from app.market_contracts.observation import PublicMarketObservation, observation_from_ohlcv
from app.market_contracts.ohlcv import OhlcvBar, build_ohlcv_bar, observation_id_for
from app.schemas.common import Timeframe
from app.signal_fusion.adapters import AssessmentCommand, evidence_window_from_assessment_command
from app.signal_fusion.enums import (
    AssertionSource,
    EvidenceAdapterKind,
    EvidenceRole,
    TenantAssertionRole,
)
from app.signal_fusion.errors import (
    ConflictingSemanticInputError,
    EvidenceIdentityMismatchError,
    FormingObservationMutationError,
    TenantAssertionSelectionError,
)
from app.signal_fusion.evidence_window import build_canonical_evidence_window_v1
from app.signal_fusion.observation import require_distinct_observation_for_finality_change
from app.signal_fusion.policy import first_slice_role_timeframes
from app.signal_fusion.types import SelectedTenantAssertion, selected_observation_from_public
from tests.support.phase5_market import (
    EVALUATED_AT,
    TRIGGER_OPEN,
    closed_bar,
    identity,
    spot_identity,
)
from tests.support.phase6_fusion import (
    MANDATORY_ROLES,
    assessment_command,
    blofin_evidence_identity,
    eth_evidence_identity,
    fusion_policy,
    public_observation,
    semantic_sources,
    tenant_assertion,
    window_kwargs,
)


def _build_window(**overrides: object):
    payload = window_kwargs()
    payload.update(overrides)
    return build_canonical_evidence_window_v1(**payload)  # type: ignore[arg-type]


def _replace_trigger(observation: PublicMarketObservation) -> AssessmentCommand:
    command = assessment_command(adapter_kind=EvidenceAdapterKind.WATCHER)
    observations = (observation, command.public_observations[1], command.public_observations[2])
    return command.model_copy(update={"public_observations": observations})


def test_wrong_venue_observation_is_rejected() -> None:
    command = _replace_trigger(public_observation(market_identity=blofin_evidence_identity()))
    with pytest.raises(EvidenceIdentityMismatchError, match="wrong venue"):
        evidence_window_from_assessment_command(command)


def test_wrong_market_observation_is_rejected() -> None:
    command = _replace_trigger(public_observation(market_identity=spot_identity()))
    with pytest.raises(EvidenceIdentityMismatchError, match="wrong market"):
        evidence_window_from_assessment_command(command)


def test_wrong_instrument_observation_is_rejected() -> None:
    command = _replace_trigger(public_observation(market_identity=eth_evidence_identity()))
    with pytest.raises(EvidenceIdentityMismatchError, match="wrong instrument"):
        evidence_window_from_assessment_command(command)


def test_trigger_and_context_may_use_different_timeframes() -> None:
    window = evidence_window_from_assessment_command(
        assessment_command(adapter_kind=EvidenceAdapterKind.WATCHER)
    )
    by_role = {item.role: item for item in window.selected_public_observations}
    assert by_role[EvidenceRole.TRIGGER_OHLCV].timeframe is Timeframe.M15
    assert by_role[EvidenceRole.CONTEXT_OHLCV].timeframe is Timeframe.H4
    assert by_role[EvidenceRole.CVD_WINDOW].timeframe is Timeframe.M15
    assert window.timeframe is Timeframe.M15


def test_wrong_timeframe_for_bound_role_is_rejected() -> None:
    command = _replace_trigger(public_observation(index=1, timeframe=Timeframe.H4))
    with pytest.raises(EvidenceIdentityMismatchError, match="wrong timeframe for role"):
        evidence_window_from_assessment_command(command)


def test_unbound_role_does_not_inherit_evidence_timeframe() -> None:
    baseline = _build_window()
    h1_identity = identity(timeframe=Timeframe.H1)
    changed = _build_window(evidence_identity=h1_identity)
    assert changed.timeframe is Timeframe.H1
    assert changed.content_hash != baseline.content_hash
    assert {item.timeframe for item in changed.selected_public_observations} == {
        Timeframe.M15,
        Timeframe.H4,
    }


def test_extraneous_tenant_assertion_does_not_change_window_hash() -> None:
    baseline = evidence_window_from_assessment_command(
        assessment_command(adapter_kind=EvidenceAdapterKind.WATCHER)
    )
    extra = evidence_window_from_assessment_command(
        assessment_command(
            adapter_kind=EvidenceAdapterKind.DETECTOR,
            tenant_assertions=(tenant_assertion(),),
        )
    )
    assert extra.content_hash == baseline.content_hash
    assert extra.tenant_assertions == ()


def test_presentation_assertion_does_not_change_window_hash() -> None:
    baseline = evidence_window_from_assessment_command(
        assessment_command(adapter_kind=EvidenceAdapterKind.WATCHER)
    )
    presentation = evidence_window_from_assessment_command(
        assessment_command(
            adapter_kind=EvidenceAdapterKind.TRADINGVIEW,
            tenant_assertions=(tenant_assertion(),),
            assertion_roles=(TenantAssertionRole.PRESENTATION,),
        )
    )
    assert presentation.content_hash == baseline.content_hash
    assert presentation.tenant_assertions == ()


def test_required_tenant_assertion_via_command_changes_window_hash() -> None:
    baseline = evidence_window_from_assessment_command(
        assessment_command(adapter_kind=EvidenceAdapterKind.WATCHER)
    )
    assertion = tenant_assertion()
    required = evidence_window_from_assessment_command(
        assessment_command(
            adapter_kind=EvidenceAdapterKind.TRADINGVIEW,
            tenant_assertions=(assertion,),
            assertion_roles=(TenantAssertionRole.TRADINGVIEW_ALERT,),
            required_assertion_roles=(TenantAssertionRole.TRADINGVIEW_ALERT,),
        )
    )
    assert required.content_hash != baseline.content_hash
    assert len(required.tenant_assertions) == 1
    assert required.tenant_assertions[0].assertion_id == assertion.assertion_id


def test_unselected_user_assertion_does_not_fork_required_assertion_identity() -> None:
    tv = tenant_assertion()
    user = tenant_assertion(
        assertion_id=uuid4(),
        source=AssertionSource.USER_ASSERTION,
        source_event_id="user-note-1",
    )
    required_only = evidence_window_from_assessment_command(
        assessment_command(
            adapter_kind=EvidenceAdapterKind.WATCHER,
            tenant_assertions=(tv,),
            assertion_roles=(TenantAssertionRole.TRADINGVIEW_ALERT,),
            required_assertion_roles=(TenantAssertionRole.TRADINGVIEW_ALERT,),
        )
    )
    with_extra = evidence_window_from_assessment_command(
        assessment_command(
            adapter_kind=EvidenceAdapterKind.DETECTOR,
            tenant_assertions=(tv, user),
            assertion_roles=(
                TenantAssertionRole.TRADINGVIEW_ALERT,
                TenantAssertionRole.USER_ASSERTION,
            ),
            required_assertion_roles=(TenantAssertionRole.TRADINGVIEW_ALERT,),
        )
    )
    assert with_extra.content_hash == required_only.content_hash
    assert len(with_extra.tenant_assertions) == 1


def test_missing_required_tenant_assertion_fails_closed() -> None:
    with pytest.raises(TenantAssertionSelectionError, match="missing"):
        evidence_window_from_assessment_command(
            assessment_command(
                adapter_kind=EvidenceAdapterKind.WATCHER,
                required_assertion_roles=(TenantAssertionRole.TRADINGVIEW_ALERT,),
            )
        )


def test_fusion_policy_rejects_presentation_as_required_assertion() -> None:
    with pytest.raises(ValidationError, match="PRESENTATION"):
        fusion_policy(required_assertion_roles=(TenantAssertionRole.PRESENTATION,))


def test_duplicate_mandatory_roles_converge() -> None:
    baseline = _build_window()
    duplicated = _build_window(
        mandatory_evidence_roles=(*MANDATORY_ROLES, EvidenceRole.TRIGGER_OHLCV)
    )
    assert duplicated.content_hash == baseline.content_hash
    assert duplicated.mandatory_evidence_roles == baseline.mandatory_evidence_roles


def test_duplicate_source_set_converge() -> None:
    baseline = _build_window()
    sources = semantic_sources()
    duplicated = _build_window(source_set=(*sources, *sources))
    assert duplicated.content_hash == baseline.content_hash
    assert duplicated.source_set == baseline.source_set


def test_duplicate_tenant_assertions_converge() -> None:
    assertion = tenant_assertion()
    selected = SelectedTenantAssertion(
        role=TenantAssertionRole.TRADINGVIEW_ALERT,
        assertion_id=assertion.assertion_id,
        content_hash=assertion.content_hash,
    )
    once = _build_window(
        tenant_assertions=(selected,),
        required_assertion_roles=(TenantAssertionRole.TRADINGVIEW_ALERT,),
    )
    duplicated = _build_window(
        tenant_assertions=(selected, selected),
        required_assertion_roles=(TenantAssertionRole.TRADINGVIEW_ALERT,),
    )
    assert duplicated.content_hash == once.content_hash
    assert len(duplicated.tenant_assertions) == 1


def test_exact_duplicate_selected_observations_converge() -> None:
    baseline = _build_window()
    duplicated = _build_window(
        selected_public_observations=(
            *baseline.selected_public_observations,
            baseline.selected_public_observations[0],
        )
    )
    assert duplicated.content_hash == baseline.content_hash
    assert duplicated.selected_public_observations == baseline.selected_public_observations


def test_distinct_observations_in_one_role_remain_legal() -> None:
    baseline = _build_window()
    extra_context = selected_observation_from_public(
        public_observation(index=3, timeframe=Timeframe.H4),
        role=EvidenceRole.CONTEXT_OHLCV,
    )
    windowed = _build_window(
        selected_public_observations=(*baseline.selected_public_observations, extra_context),
        role_timeframes=first_slice_role_timeframes(),
    )
    assert windowed.content_hash != baseline.content_hash
    context_count = sum(
        1
        for item in windowed.selected_public_observations
        if item.role is EvidenceRole.CONTEXT_OHLCV
    )
    assert context_count == 2


def test_conflicting_tenant_assertion_hashes_fail_closed() -> None:
    assertion = tenant_assertion()
    with pytest.raises(ConflictingSemanticInputError, match="Conflicting tenant assertion"):
        _build_window(
            tenant_assertions=(
                SelectedTenantAssertion(
                    role=TenantAssertionRole.TRADINGVIEW_ALERT,
                    assertion_id=assertion.assertion_id,
                    content_hash="aa" * 32,
                ),
                SelectedTenantAssertion(
                    role=TenantAssertionRole.TRADINGVIEW_ALERT,
                    assertion_id=assertion.assertion_id,
                    content_hash="bb" * 32,
                ),
            ),
            required_assertion_roles=(TenantAssertionRole.TRADINGVIEW_ALERT,),
        )


def test_duplicate_transport_input_cannot_fork_canonical_window() -> None:
    kwargs = window_kwargs()
    selected = kwargs["selected_public_observations"]
    sources = kwargs["source_set"]
    left = _build_window()
    right = _build_window(
        mandatory_evidence_roles=(*MANDATORY_ROLES, EvidenceRole.CONTEXT_OHLCV),
        selected_public_observations=(*selected, selected[0], selected[-1]),  # type: ignore[misc]
        source_set=(*sources, *sources),  # type: ignore[misc]
        role_timeframes=first_slice_role_timeframes(),
    )
    assert left.content_hash == right.content_hash


def _envelope(
    bar: OhlcvBar,
    *,
    identity_value: EvidenceMarketIdentity | None = None,
) -> PublicMarketObservation:
    return observation_from_ohlcv(
        bar,
        identity=identity_value or identity(),
        observed_at=EVALUATED_AT,
        receive_time=EVALUATED_AT,
        freshness_state=FreshnessState.FRESH,
    )


def test_phase6_forming_and_final_are_distinct_immutable_observations() -> None:
    forming_bar = build_ohlcv_bar(
        instrument=binance_usdm_btcusdt(),
        timeframe=Timeframe.M15,
        interval_start=TRIGGER_OPEN,
        open_=Decimal("100000"),
        high=Decimal("100010"),
        low=Decimal("99990"),
        close=Decimal("100005"),
        base_volume=Decimal("10"),
        quote_volume=Decimal("1000000"),
        evaluated_at=TRIGGER_OPEN + timedelta(minutes=5),
        grace=timedelta(0),
        provider_complete=False,
    )
    final_bar = closed_bar()
    forming = _envelope(forming_bar)
    final = _envelope(final_bar)
    assert forming.source_event_id == final.source_event_id
    assert forming.observation_id != final.observation_id
    require_distinct_observation_for_finality_change(forming, final)
    mutated = forming.model_copy(update={"finality": Finality.FINAL})
    with pytest.raises(FormingObservationMutationError, match="cannot mutate"):
        require_distinct_observation_for_finality_change(forming, mutated)


def test_phase6_corrected_revision_is_a_new_immutable_observation() -> None:
    first_bar = closed_bar(revision=1)
    corrected_bar = with_content_hash(
        first_bar.model_copy(
            update={"revision": 2, "finality": Finality.CORRECTED, "content_hash": "0" * 64}
        )
    )
    first = _envelope(first_bar)
    corrected = _envelope(corrected_bar)
    assert first.source_event_id == corrected.source_event_id
    assert first.observation_id != corrected.observation_id
    require_distinct_observation_for_finality_change(first, corrected)


def test_phase6_replay_of_same_revision_keeps_observation_identity() -> None:
    bar = closed_bar(revision=1)
    first = _envelope(bar)
    second = _envelope(bar)
    assert first.observation_id == second.observation_id
    assert first.observation_id == observation_id_for(
        bar.source_event_id, finality=Finality.FINAL, revision=1
    )
    assert observation_id_for(bar.source_event_id) != first.observation_id
