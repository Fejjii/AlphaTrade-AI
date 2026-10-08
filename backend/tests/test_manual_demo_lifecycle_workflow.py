"""Durable manual history, scoped Agent selection and evidence-backed recovery."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select, text

from app.core.errors import NotFoundError, TradingPolicyError
from app.db.models import (
    AccountRiskAccountingState,
    ExecutionFillFact,
    JournalTrade,
    KillSwitchState,
    ManualDemoLifecycleResolution,
    RiskReservation,
)
from app.interactive_agent.actions import RecordedTradeInput
from app.interactive_agent.contracts import AgentTurnRequest
from app.interactive_agent.manual_demo_selection import manual_selectors
from app.interactive_agent.recorded_trade import read_recorded_trade
from app.interactive_agent.service import InteractiveAgentService
from app.schemas.common import JournalTradeStatus
from app.schemas.manual_demo import ManualDemoHistoryFilter, ManualDemoPreviewRequest
from app.security.tenant import TenantContext
from app.services.demo_account_history import has_demo_entry_history
from app.services.manual_demo_history import ManualDemoHistoryService
from tests.support.postgres_persistence import requires_postgres
from tests.test_manual_blofin_demo import confirmation
from tests.test_manual_blofin_demo import world as world
from tests.test_manual_demo_reconciliation import LIVE_TIME, LIVE_TS, _service, _submit
from tests.test_manual_demo_reconciliation import native as native

pytestmark = requires_postgres


def two_attempts(native):
    world, _ = native
    with world[0]() as session:
        svc = _service(world, session)
        original = svc.preview(
            world[1],
            ManualDemoPreviewRequest(side="BUY", quantity="0.1", stop="82000", target="83000"),
        )
        later = svc.preview(
            world[1],
            ManualDemoPreviewRequest(side="BUY", quantity="1", stop="82000", target="83000"),
        )
        snapshot = world[4].snapshot(
            symbol="BTCUSDT", now=world[4]._clock(), side=original.side, quantity=Decimal("1")
        )
    with world[0]() as session:
        first = _service(world, session).confirm(world[1], confirmation(original))
    # Simulate a competing claimant whose flat preflight preceded the first send.
    old_snapshot = world[4].snapshot
    world[4].snapshot = lambda **kwargs: snapshot
    try:
        with world[0]() as session:
            blocked = _service(world, session).confirm(world[1], confirmation(later))
    finally:
        world[4].snapshot = old_snapshot
    assert blocked.status == "demo_account_already_claimed" and world[3].post_count == 1
    return first, blocked


def set_exit(
    native, first, *, quantity="0.1", flat=True, category="normal", protection_state="canceled"
):
    world, changes = native
    world[3].clock_delta = 60
    entry = {
        "orderId": "28697026",
        "clientOrderId": first.client_order_id,
        "instId": "BTC-USDT",
        "side": "buy",
        "positionSide": "net",
        "marginMode": "cross",
        "orderType": "market",
        "size": "0.1",
        "filledSize": "0.1",
        "state": "filled",
        "createTime": LIVE_TS,
    }
    close = {
        "orderId": "390001",
        "clientOrderId": "venue-exit",
        "instId": "BTC-USDT",
        "side": "sell",
        "positionSide": "net",
        "marginMode": "cross",
        "orderType": "market",
        "size": quantity,
        "filledSize": quantity,
        "reduceOnly": "true",
        "state": "filled",
        "createTime": str(int(LIVE_TS) + 30000),
        "orderCategory": category,
        "tpTriggerPrice": "83000",
        "slTriggerPrice": "82000",
    }
    changes["response"].update(
        {
            "/api/v1/account/positions": []
            if flat
            else [
                {
                    "instId": "BTC-USDT",
                    "positionSide": "net",
                    "marginMode": "cross",
                    "positions": "0.05",
                }
            ],
            "/api/v1/trade/orders-tpsl-pending": [],
            "/api/v1/trade/orders-history": [entry, close],
            "/api/v1/trade/orders-tpsl-history": [
                {
                    "tpslId": "2411",
                    "clientOrderId": None,
                    "instId": "BTC-USDT",
                    "positionSide": "net",
                    "marginMode": "cross",
                    "side": "sell",
                    "state": protection_state,
                    "actualSize": quantity,
                    "createTime": LIVE_TS,
                    "tpTriggerPrice": "83000",
                    "slTriggerPrice": "82000",
                }
            ],
        }
    )
    old = world[4]._client._transport.handler

    def transport(request):
        if (
            request.url.path.endswith("fills-history")
            and request.url.params.get("orderId") == "390001"
        ):
            changes["reads"].append((request.method, request.url.path))
            return httpx.Response(
                200,
                json={
                    "code": "0",
                    "data": [
                        {
                            "orderId": "390001",
                            "tradeId": "exit-1",
                            "instId": "BTC-USDT",
                            "positionSide": "net",
                            "side": "sell",
                            "fillPrice": "83000.000000000000000000",
                            "fillSize": quantity,
                            "fee": "-0.00498",
                            "fillPnl": "0.0106",
                            "ts": str(int(LIVE_TS) + 31000),
                        }
                    ],
                },
            )
        return old(request)

    world[4]._client._transport.handler = transport
    return entry, close


def test_history_new_session_pagination_distinguishes_original_and_blocked_without_venue_io(native):
    world, changes = native
    first, blocked = two_attempts(native)
    changes["reads"].clear()
    for _ in range(2):
        with world[0]() as session:
            history = ManualDemoHistoryService(session)
            page = history.list(world[1], ManualDemoHistoryFilter(limit=1))
            older = history.list(world[1], ManualDemoHistoryFilter(limit=1, offset=1))
            assert page.total == 2 and {page.items[0].command_id, older.items[0].command_id} == {
                first.command_id,
                blocked.command_id,
            }
            original = history.get(world[1], first.command_id)
            later = history.get(world[1], blocked.command_id)
            assert original.requested_contracts == Decimal(
                ".1"
            ) and original.base_quantity == Decimal(".0001")
            assert original.evidence.journal_trade_id == first.journal_trade_id
            assert (
                later.requested_contracts == 1
                and later.evidence.execution_status == "blocked_before_submission"
            )
            assert (
                later.evidence.journal_trade_id is None
                and later.submitted_at is None
                and not later.evidence.can_cancel
            )
            assert original.detail_url.endswith(str(first.command_id))
    assert not changes["reads"]


def test_filters_before_latest_and_limit_and_precise_natural_agent_request(native):
    world, _ = native
    first, blocked = two_attempts(native)
    with world[0]() as session:
        history = ManualDemoHistoryService(session)
        for status in ("submitted", "filled"):
            page = history.list(
                world[1], ManualDemoHistoryFilter(submission_status=status, limit=1)
            )
            assert page.total == 1 and page.items[0].command_id == first.command_id
        assert (
            history.list(world[1], ManualDemoHistoryFilter(submission_status="blocked", limit=1))
            .items[0]
            .command_id
            == blocked.command_id
        )
        filters = ManualDemoHistoryFilter(
            requested_quantity=".1",
            since=LIVE_TIME - timedelta(minutes=5),
            until=LIVE_TIME + timedelta(minutes=5),
            limit=1,
        )
        assert history.list(world[1], filters).items[0].command_id == first.command_id
        response = InteractiveAgentService(session, settings=world[2]).handle_turn(
            AgentTurnRequest(
                message=(
                    "Explain my manual BloFin demo BTC long order from 8 October 2026 "
                    "around 12:56 UTC, 0.1 contracts"
                )
            ),
            organization_id=world[1].organization_id,
            user_id=world[1].user_id,
        )
        assert str(first.command_id) in response.reply and "Multiple manual" not in response.reply
        assert str(blocked.command_id) not in response.reply


def test_ambiguity_has_bounded_selectable_command_choices(native):
    world, _ = native
    first, blocked = two_attempts(native)
    with world[0]() as session:
        result = read_recorded_trade(
            session,
            RecordedTradeInput(trade_origin="manual_demo_test", execution_venue="BLOFIN_DEMO"),
            organization_id=world[1].organization_id,
            user_id=world[1].user_id,
        )
        assert "Multiple manual" in result.reply and "blocked_before_submission" in result.reply
        assert {r.record_id for r in result.connections} == {
            str(first.command_id),
            str(blocked.command_id),
        }
        assert (
            all(r.relation == "manual demo choice" for r in result.connections)
            and not result.allow_model
        )


def test_command_before_journal_persists_for_followup(native):
    world, changes = native
    changes["failure"] = "/api/v1/trade/fills-history"
    _, first = _submit(native)
    assert first.journal_trade_id is None
    with world[0]() as session:
        selected = InteractiveAgentService(session, settings=world[2]).handle_turn(
            AgentTurnRequest(message=f"Explain command {first.command_id}"),
            organization_id=world[1].organization_id,
            user_id=world[1].user_id,
        )
        session.commit()
    with world[0]() as session:
        followup = InteractiveAgentService(session, settings=world[2]).handle_turn(
            AgentTurnRequest(
                message="Explain that trade", conversation_id=selected.conversation_id
            ),
            organization_id=world[1].organization_id,
            user_id=world[1].user_id,
        )
        assert (
            str(first.command_id) in followup.reply
            and "no unambiguous selected trade" not in followup.reply
        )
        assert followup.proposals == []


@pytest.mark.parametrize("case", ["other_tenant", "other_user", "unknown"])
def test_history_and_agent_tenant_isolation(native, case):
    world, changes = native
    _, first = _submit(native)
    tenant = TenantContext(
        world[1].user_id if case != "other_user" else uuid4(),
        world[1].organization_id if case != "other_tenant" else uuid4(),
        "test",
        world[1].membership_role,
    )
    target = uuid4() if case == "unknown" else first.command_id
    changes["reads"].clear()
    with world[0]() as session:
        with pytest.raises(NotFoundError):
            ManualDemoHistoryService(session).get(tenant, target)
        read = read_recorded_trade(
            session,
            RecordedTradeInput(command_id=target),
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
        )
        assert "No matching" in read.reply
    assert not changes["reads"]


def test_flatness_and_canceled_protection_never_fabricate_exit(native):
    world, changes = native
    _, first = _submit(native)
    entry, _ = set_exit(native, first)
    changes["response"]["/api/v1/trade/orders-history"] = [entry]
    with world[0]() as session:
        current = _service(world, session).reconcile(world[1], first.command_id)
        assert (
            current.position_status == "flat_exit_unverified"
            and current.exit_quantity == 0
            and not current.can_resolve
        )
        trade = session.get(JournalTrade, first.journal_trade_id)
        assert trade.status == JournalTradeStatus.OPEN and trade.exit_price is None
        with pytest.raises(TradingPolicyError):
            _service(world, session).resolve(world[1], first.command_id)
    assert world[3].post_count == 1


@pytest.mark.parametrize(
    "category,protection_state", [("normal", "canceled"), ("tp", "effective"), ("sl", "effective")]
)
def test_verified_exit_release_once_preserves_unrelated_accounting_and_global_kill(
    native, category, protection_state
):
    world, changes = native
    _, first = _submit(native)
    set_exit(native, first, category=category, protection_state=protection_state)
    with world[0]() as session:
        accounting = session.scalars(select(AccountRiskAccountingState)).one()
        original = accounting.actual_notional
        accounting.actual_notional += 50
        accounting.symbol_actual = {**accounting.symbol_actual, "ETH-USDT": "50"}
        accounting.reserved_notional += 25
        accounting.symbol_reserved = {**accounting.symbol_reserved, "ETH-USDT": "25"}
        session.add(
            KillSwitchState(
                organization_id=world[1].organization_id,
                active=True,
                reason="Unrelated operator hold",
                version=17,
            )
        )
        session.commit()
    changes["reads"].clear()
    with world[0]() as session:
        current = _service(world, session).reconcile(world[1], first.command_id)
        assert current.position_status == "closed_verified" and current.can_resolve
        assert current.exit_quantity == Decimal(".1") and current.exit_fees == Decimal("-.00498")
        assert session.get(JournalTrade, first.journal_trade_id).status == JournalTradeStatus.CLOSED
        resolved = _service(world, session).resolve(world[1], first.command_id)
        assert resolved.recovery_status == "resolved" and resolved.execution_status == "closed"
    for _ in range(2):
        with world[0]() as session:
            assert (
                _service(world, session).resolve(world[1], first.command_id).journal_trade_id
                == first.journal_trade_id
            )
            assert (
                _service(world, session).reconcile(world[1], first.command_id).execution_status
                == "closed"
            )
    with world[0]() as session:
        assert session.scalar(select(func.count()).select_from(ManualDemoLifecycleResolution)) == 1
        assert session.scalar(select(func.count()).select_from(ExecutionFillFact)) == 1
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 1
        reservation = session.scalars(select(RiskReservation)).one()
        assert reservation.release_state.value == "RELEASED"
        accounting = session.scalars(select(AccountRiskAccountingState)).one()
        assert accounting.actual_notional == 50
        assert Decimal("25") <= accounting.reserved_notional <= Decimal("25.00000001")
        assert (
            accounting.symbol_actual["ETH-USDT"] == "50"
            and accounting.symbol_reserved["ETH-USDT"] == "25"
        )
        kill = session.scalars(select(KillSwitchState)).one()
        assert kill.active and kill.version == 17 and kill.reason == "Unrelated operator hold"
        trade = session.get(JournalTrade, first.journal_trade_id)
        assert trade.exit_price == 83000 and trade.net_pnl is None and trade.funding is None
        assert not has_demo_entry_history(
            session, organization_id=world[1].organization_id, account_id=reservation.account_id
        )
        released = session.scalars(select(ManualDemoLifecycleResolution)).one().released_notional
        assert original <= released < original + Decimal("0.1")
        with pytest.raises(Exception, match="alphatrade_immutable_history"), session.begin_nested():
            session.execute(text("DELETE FROM manual_demo_lifecycle_resolutions"))
    assert all(method == "GET" for method, _ in changes["reads"]) and world[3].post_count == 1


def test_read_failure_retains_entry_and_unknown_claim(native):
    world, changes = native
    _, first = _submit(native)
    set_exit(native, first)
    changes["failure"] = "/api/v1/trade/orders-history"
    with world[0]() as session:
        result = _service(world, session).reconcile(world[1], first.command_id)
        assert result.filled_quantity == Decimal(".1") and result.exit_quantity == 0
        assert not result.can_resolve and result.reconciliation_diagnostics
        with pytest.raises(TradingPolicyError):
            _service(world, session).resolve(world[1], first.command_id)
        assert session.scalar(select(func.count()).select_from(ManualDemoLifecycleResolution)) == 0
        assert has_demo_entry_history(
            session,
            organization_id=world[1].organization_id,
            account_id=world[2].governed_blofin_demo_account_id,
        )


def test_blocked_resolution_never_releases_original_account_claim(native):
    world, changes = native
    _first, blocked = two_attempts(native)
    changes["response"]["/api/v1/trade/orders-tpsl-pending"] = []
    with world[0]() as session:
        resolved = _service(world, session).resolve(world[1], blocked.command_id)
        assert (
            resolved.recovery_status == "resolved"
            and resolved.execution_status == "blocked_before_submission"
        )
        assert (
            session.scalars(select(ManualDemoLifecycleResolution)).one().command_id
            == blocked.command_id
        )
        assert has_demo_entry_history(
            session,
            organization_id=world[1].organization_id,
            account_id=world[2].governed_blofin_demo_account_id,
        )
        assert session.scalar(select(func.count()).select_from(RiskReservation)) == 1
    assert world[3].post_count == 1


def test_unsupported_time_filter_is_explicit_and_structured_timezone_required():
    result = manual_selectors("Explain manual BloFin demo order at 12:56 UTC with 0.1 contracts")
    assert (
        Decimal(result["requested_quantity"]) == Decimal(".1")
        and result["unsupported_filters"]
        and "since" not in result
    )
    with pytest.raises(ValueError, match="timezone"):
        RecordedTradeInput(since="2026-10-08T12:56:00")


def test_proven_unsent_fences_dispatch_releases_once_and_permits_next_preview(native, monkeypatch):
    from app.db.models import VenueSubmitEffect
    from app.services.venue_submit_dispatcher import VenueSubmitDispatcher

    world, changes = native
    monkeypatch.setattr(
        VenueSubmitDispatcher,
        "authorize_dispatch",
        lambda self, **kwargs: self._require_effect(kwargs["command_id"]),
    )
    _, attempt = _submit(native)
    assert world[3].post_count == 0
    with world[0]() as session:
        token = session.scalars(select(VenueSubmitEffect)).one().fencing_token
        resolved = _service(world, session).resolve(world[1], attempt.command_id)
        assert (
            resolved.recovery_status == "resolved"
            and resolved.execution_status == "blocked_before_submission"
        )
        effect = session.scalars(select(VenueSubmitEffect)).one()
        assert effect.state.value == "PROVEN_UNSENT" and effect.fencing_token > token
        assert effect.dispatch_authorized_at is None
        assert session.scalars(select(RiskReservation)).one().release_state.value == "RELEASED"
        again = _service(world, session).resolve(world[1], attempt.command_id)
        assert again.command_id == attempt.command_id
        assert session.scalar(select(func.count()).select_from(ManualDemoLifecycleResolution)) == 1
        next_plan = _service(world, session).preview(
            world[1],
            ManualDemoPreviewRequest(side="BUY", quantity=".1", stop="82000", target="83000"),
        )
        assert next_plan.revision_id != attempt.revision_id
    assert world[3].post_count == 0 and all(method == "GET" for method, _ in changes["reads"])


@pytest.mark.parametrize("state", ["canceled", "rejected", "expired"])
def test_native_terminal_unfilled_resolution_without_journal_or_duplicate_release(native, state):
    from app.db.models import ExecutionTransition

    world, changes = native
    changes["order"].update(state=state, filledSize="0")
    changes["response"]["/api/v1/trade/fills-history"] = []
    changes["response"]["/api/v1/trade/orders-tpsl-pending"] = []
    _, first = _submit(native)
    with world[0]() as session:
        before = session.scalar(select(func.count()).select_from(ExecutionTransition))
        for _ in range(2):
            result = _service(world, session).reconcile(world[1], first.command_id)
            assert (
                result.filled_quantity == 0
                and result.journal_trade_id is None
                and result.can_resolve
            )
        assert session.scalar(select(func.count()).select_from(ExecutionTransition)) == before
        resolved = _service(world, session).resolve(world[1], first.command_id)
        assert resolved.recovery_status == "resolved"
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 0
    assert world[3].post_count == 1


def test_partial_exit_replay_retains_native_exit_facts_and_fees_during_read_outage(native):
    from app.db.models import AuditLog

    world, changes = native
    _, first = _submit(native)
    set_exit(native, first, quantity=".05", flat=False)
    for _ in range(2):
        with world[0]() as session:
            partial = _service(world, session).reconcile(world[1], first.command_id)
            assert partial.exit_quantity == Decimal(".05") and not partial.can_resolve
            assert (
                session.get(JournalTrade, first.journal_trade_id).status == JournalTradeStatus.OPEN
            )
    changes["failure"] = "/api/v1/trade/orders-history"
    with world[0]() as session:
        failed = _service(world, session).reconcile(world[1], first.command_id)
        assert failed.exit_quantity == Decimal(".05") and failed.exit_fees == Decimal("-.00498")
        assert failed.reconciliation_freshness == "latest_read_failed"
        assert session.get(JournalTrade, first.journal_trade_id).fees == Decimal(
            ".00497364"
        ) - Decimal(".00498")
        exit_count = session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.redacted_metadata["operation"].as_string() == "manual_demo_exit_fill")
        )
        assert exit_count == 1
        with pytest.raises(TradingPolicyError):
            _service(world, session).resolve(world[1], first.command_id)
    assert world[3].post_count == 1


@pytest.mark.parametrize(
    "bad_case",
    ["incomplete_page", "second_opening", "protection_not_effective", "position_present"],
)
def test_incomplete_or_unexplained_lifecycle_never_releases_the_claim(native, bad_case):
    world, changes = native
    _, first = _submit(native)
    entry, close = set_exit(native, first, category="tp", protection_state="effective")
    if bad_case == "incomplete_page":
        changes["response"]["/api/v1/trade/orders-history"] = [entry] * 100
    elif bad_case == "second_opening":
        changes["response"]["/api/v1/trade/orders-history"] = [
            entry,
            close,
            {**close, "orderId": "other-open", "side": "buy", "reduceOnly": "false"},
        ]
    elif bad_case == "protection_not_effective":
        changes["response"]["/api/v1/trade/orders-tpsl-history"][0]["state"] = "canceled"
    else:
        changes["response"]["/api/v1/account/positions"] = [
            {"instId": "BTC-USDT", "positions": ".1", "positionSide": "net", "marginMode": "cross"}
        ]
    with world[0]() as session:
        result = _service(world, session).reconcile(world[1], first.command_id)
        assert not result.can_resolve
        with pytest.raises(TradingPolicyError):
            _service(world, session).resolve(world[1], first.command_id)
        assert session.scalar(select(func.count()).select_from(ManualDemoLifecycleResolution)) == 0


def test_local_unsent_fence_retains_reservation_when_account_state_is_unknown(native, monkeypatch):
    from app.db.models import VenueSubmitEffect
    from app.services.venue_submit_dispatcher import VenueSubmitDispatcher

    world, _ = native
    monkeypatch.setattr(
        VenueSubmitDispatcher,
        "authorize_dispatch",
        lambda self, **kwargs: self._require_effect(kwargs["command_id"]),
    )
    _, attempt = _submit(native)
    prior = world[4]._client._transport.handler
    world[4]._client._transport.handler = lambda request: (
        httpx.Response(503, json={"code": "500", "data": []})
        if request.url.path == "/api/v1/account/positions"
        else prior(request)
    )
    with world[0]() as session:
        reserved = session.scalars(select(RiskReservation)).one().remaining_reserved_notional
        with pytest.raises(TradingPolicyError):
            _service(world, session).resolve(world[1], attempt.command_id)
        assert session.scalars(select(VenueSubmitEffect)).one().state.value == "PROVEN_UNSENT"
        reservation = session.scalars(select(RiskReservation)).one()
        assert reservation.release_state.value == "CHARGED"
        assert reservation.remaining_reserved_notional == reserved
        assert session.scalar(select(func.count()).select_from(ManualDemoLifecycleResolution)) == 0
    assert world[3].post_count == 0


def test_later_exit_read_failure_does_not_reactivate_global_hold_for_recorded_closed_position(
    native,
):
    world, changes = native
    _, first = _submit(native)
    set_exit(native, first)
    with world[0]() as session:
        result = _service(world, session).reconcile(world[1], first.command_id)
        assert result.execution_status == "closed"
        kill = session.scalars(select(KillSwitchState)).one_or_none()
        version = kill.version if kill else None
    changes["failure"] = "/api/v1/trade/orders-history"
    with world[0]() as session:
        result = _service(world, session).reconcile(world[1], first.command_id)
        assert result.execution_status == "closed" and result.exit_quantity == Decimal(".1")
        assert result.account_status == "unknown" and not result.can_resolve
        kill = session.scalars(select(KillSwitchState)).one_or_none()
        assert (kill.version if kill else None) == version
        assert session.scalar(select(func.count()).select_from(ManualDemoLifecycleResolution)) == 0


def test_history_http_auth_scope_and_invalid_date_range_are_actionable(native):
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.db.session import get_session
    from app.main import create_app
    from app.security.tokens import create_access_token

    world, changes = native
    first, blocked = two_attempts(native)
    settings = Settings(
        _env_file=None,
        environment="local",
        provider_mode="mock",
        execution_mode="paper",
        enable_real_trading=False,
        rate_limit_use_redis=False,
        market_data_cache_use_redis=False,
        access_token_denylist_use_redis=False,
        require_email_verified=False,
    )
    app = create_app(settings=settings)

    def sessions():
        with world[0]() as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    token, _ = create_access_token(
        user_id=world[1].user_id,
        organization_id=world[1].organization_id,
        email=world[1].email,
        settings=settings,
    )
    headers = {"Authorization": f"Bearer {token}"}
    changes["reads"].clear()
    with TestClient(app) as client:
        assert client.get("/execution/manual-demo/commands").status_code == 401
        assert client.get(f"/execution/manual-demo/commands/{first.command_id}").status_code == 401
        page = client.get(
            "/execution/manual-demo/commands",
            headers=headers,
            params={"limit": 1, "requested_quantity": "0.1"},
        )
        assert page.status_code == 200 and page.json()["total"] == 1
        assert page.json()["items"][0]["command_id"] == str(first.command_id)
        for params in (
            {"since": "2026-10-08T12:56:00"},
            {"since": "2026-10-09T00:00:00Z", "until": "2026-10-08T00:00:00Z"},
        ):
            invalid = client.get("/execution/manual-demo/commands", headers=headers, params=params)
            assert (
                invalid.status_code == 422 and invalid.json()["error"]["code"] == "validation_error"
            )
        assert (
            client.get(f"/execution/manual-demo/commands/{uuid4()}", headers=headers).status_code
            == 404
        )
        assert (
            client.get(
                f"/execution/manual-demo/commands/{blocked.command_id}", headers=headers
            ).status_code
            == 200
        )
    assert not changes["reads"] and world[3].post_count == 1


def test_latest_observation_can_return_to_previous_protection_receipt_without_duplicate_economics(
    native,
):
    world, changes = native
    _, first = _submit(native)
    changes["response"]["/api/v1/trade/orders-tpsl-pending"] = []
    with world[0]() as session:
        failed = _service(world, session).reconcile(world[1], first.command_id)
        assert failed.protection == "missing"
        assert (
            ManualDemoHistoryService(session).get(world[1], first.command_id).evidence.protection
            == "missing"
        )
    del changes["response"]["/api/v1/trade/orders-tpsl-pending"]
    with world[0]() as session:
        restored = _service(world, session).reconcile(world[1], first.command_id)
        assert restored.protection == "verified"
        detail = ManualDemoHistoryService(session).get(world[1], first.command_id)
        assert detail.evidence.protection == "verified"
        agent = read_recorded_trade(
            session,
            RecordedTradeInput(command_id=first.command_id),
            organization_id=world[1].organization_id,
            user_id=world[1].user_id,
        )
        assert "Recorded protection: verified" in agent.reply
        assert session.scalar(select(func.count()).select_from(ExecutionFillFact)) == 1
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 1
    assert world[3].post_count == 1


def test_editable_journal_exit_does_not_prove_closure_or_suppress_protection_hold(native):
    world, changes = native
    _, first = _submit(native)
    with world[0]() as session:
        trade = session.get(JournalTrade, first.journal_trade_id)
        trade.exit_price = 83000
        trade.status = JournalTradeStatus.CLOSED
        session.commit()
    changes["response"]["/api/v1/trade/orders-tpsl-pending"] = []
    with world[0]() as session:
        result = _service(world, session).reconcile(world[1], first.command_id)
        assert result.execution_status == "filled" and result.exit_quantity == 0
        assert not result.can_resolve
        assert session.scalars(select(KillSwitchState)).one().active
    assert world[3].post_count == 1
