"""Scoped durability, overlap/restart, account switching, and real authenticated routing."""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.api.routes.blofin_activity import router
from app.core.auth import get_current_tenant
from app.core.config import get_settings
from app.core.errors import ValidationAppError, register_exception_handlers
from app.db.base import Base
from app.db.blofin_activity import BloFinActivityAccount, BloFinActivityCursor, BloFinActivityFact
from app.db.models import Organization
from app.db.session import get_session
from app.schemas.common import MembershipRole
from app.security.tenant import TenantContext
from app.services.blofin_activity_config import (
    ActivityScope,
    BloFinActivitySettings,
    credential_binding,
    get_activity_settings,
)
from app.services.blofin_activity_service import read_activity, run_activity_sync
from tests.test_blofin_activity_provider import (
    MS,
    NOW,
    HistoryVenue,
    fill,
    order,
    readonly_settings,
)


@pytest.fixture
def world():
    url = os.environ.get("BLOFIN_ACTIVITY_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set BLOFIN_ACTIVITY_TEST_POSTGRES_URL to disposable PostgreSQL.")
    admin = create_engine(url)
    schema = "activity_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(engine)
    org_id = uuid4()
    with Session(engine) as session:
        session.add(Organization(id=org_id, name="Activity fixture organization"))
        session.commit()
    venue = HistoryVenue()
    settings = readonly_settings()
    config = BloFinActivitySettings(
        _env_file=None,
        enabled=True,
        organization_id=org_id,
        expected_uid=venue.uid,
    )
    scope = ActivityScope(org_id, venue.uid)
    yield engine, settings, config, scope, venue
    engine.dispose()
    with admin.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()


def sync(world, **kwargs):
    engine, settings, config, _, venue = world
    return run_activity_sync(
        engine, settings, config, provider=venue.provider(), clock=lambda: NOW, **kwargs
    )


def page(world, **kwargs):
    engine, settings, _, scope, _ = world
    with Session(engine) as session:
        return read_activity(
            session,
            scope=scope,
            binding=credential_binding(settings),
            kind="fill",
            now=NOW,
            **kwargs,
        )


def test_overlap_replay_and_two_partial_fills_converge(world):
    venue = world[4]
    venue.pages["fill"] = {
        None: [fill("f3"), fill("f2")],
        "f2": [fill("f2"), fill("f1")],
        "f1": [],
    }
    assert sync(world).pages_committed == 4
    assert sync(world).status == "bounded"
    result = page(world)
    assert {i.trade_id for i in result.items} == {"f1", "f2", "f3"}
    assert all(i.origin == "native" and i.command_id is None for i in result.items)
    assert result.identity_status == "verified" and result.partial_coverage
    assert result.items[0].contract_multiplier == "0.001000000000000000"
    assert result.items[0].fee_currency is None and result.items[0].funding is None
    with Session(world[0]) as session:
        assert session.scalar(select(func.count()).select_from(BloFinActivityFact)) == 4
    # Replayed windows cannot add a second accounting record.
    sync(world)
    assert len(page(world).items) == 3


def test_shutdown_after_committed_page_resumes_same_window(world):
    first_config = world[2].model_copy(update={"max_pages": 1})
    assert (
        run_activity_sync(
            world[0], world[1], first_config, provider=world[4].provider(), clock=lambda: NOW
        ).pages_committed
        == 1
    )
    stop = Event()
    world[4].on_page = stop.set
    assert sync(world, shutdown=stop.is_set).status == "interrupted"
    with Session(world[0]) as session:
        cursor = session.get(BloFinActivityCursor, (*world[3].key(), "order"))
        assert cursor.native_cursor == "o1" and not cursor.window_complete
        assert session.scalar(select(func.count()).select_from(BloFinActivityFact)) == 1
    world[4].on_page = lambda: None
    assert sync(world).status == "bounded"
    assert len(page(world).items) == 1
    native_requests = [r for r in world[4].requests if r.url.path.endswith("orders-history")]
    assert any(r.url.params.get("after") == "o1" for r in native_requests)


def test_conflicting_page_rolls_back_all_new_facts_and_does_not_advance(world):
    assert sync(world).status == "bounded"
    before = page(world).coverage[1].last_successful_sync
    world[4].pages["fill"][None] = [fill("f2"), fill("f1", fee="999")]
    result = sync(world)
    assert result.status == "failed" and result.error_code == "native_identity_conflict"
    stored = page(world)
    assert [i.trade_id for i in stored.items] == ["f1"]
    assert stored.coverage[1].native_cursor is None
    assert stored.coverage[1].last_successful_sync == before
    assert stored.coverage[1].last_error_code == "native_identity_conflict"
    assert stored.freshness == "stale"


def test_fill_order_instrument_conflict_is_visible(world):
    world[4].pages["fill"][None] = [fill(instId="ETH-USDT")]
    assert sync(world).error_code == "native_identity_conflict"
    assert page(world).items == []


def test_rotation_same_uid_resumes_but_new_uid_never_reuses_scope(world):
    assert sync(world).status == "bounded"
    engine, settings, config, scope, venue = world
    rotated = settings.model_copy(update={"blofin_readonly_api_key": "rotated-fixture-key"})
    with Session(engine) as session:
        assert (
            read_activity(
                session, scope=scope, binding=credential_binding(rotated), kind="fill"
            ).items
            == []
        )
    assert (
        run_activity_sync(
            engine, rotated, config, provider=venue.provider(), clock=lambda: NOW
        ).status
        == "bounded"
    )
    with Session(engine) as session:
        assert (
            len(
                read_activity(
                    session, scope=scope, binding=credential_binding(rotated), kind="fill", now=NOW
                ).items
            )
            == 1
        )
    venue.identity["uid"] = "demo-user-2"
    assert (
        run_activity_sync(
            engine, rotated, config, provider=venue.provider(), clock=lambda: NOW
        ).error_code
        == "identity_unverified"
    )
    with Session(engine) as session:
        assert (
            read_activity(
                session, scope=scope, binding=credential_binding(rotated), kind="fill"
            ).items
            == []
        )
    new_scope = ActivityScope(scope.organization_id, "demo-user-2")
    new_config = config.model_copy(update={"expected_uid": new_scope.account_uid})
    # Same native IDs may exist on another account and form independent facts/cursors.
    assert (
        run_activity_sync(
            engine, rotated, new_config, provider=venue.provider(), clock=lambda: NOW
        ).status
        == "bounded"
    )
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(BloFinActivityFact)) == 4
        assert (
            session.get(BloFinActivityCursor, (*new_scope.key(), "fill")).window_begin_ms
            == MS - 7 * 86400000
        )


def test_initial_missing_identity_never_creates_facts(world):
    world[4].identity = {"readOnly": 1}
    assert sync(world).error_code == "identity_unverified"
    result = page(world)
    assert result.items == [] and result.identity_status == "unverified"
    assert result.identity_error_code == "identity_unverified"
    with Session(world[0]) as session:
        assert session.scalar(select(func.count()).select_from(BloFinActivityFact)) == 0
        assert session.get(BloFinActivityAccount, world[3].key()).identity_verified_at is None


def test_rate_limit_backoff_persists_and_stops_network(world):
    world[4].fail_kind = "fill"
    assert sync(world).error_code == "rate_limited"
    requests = len(world[4].requests)
    assert sync(world).status == "backoff"
    assert len(world[4].requests) == requests
    result = page(world)
    assert result.coverage[1].next_retry_at == NOW + timedelta(seconds=300)
    assert result.coverage[1].last_successful_sync is None


def test_account_lock_refuses_competing_worker_without_network(world):
    scope = world[3]
    lock_id = int.from_bytes(hashlib.sha256(str(scope.key()).encode()).digest()[:8], "big") >> 1
    with world[0].connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_id})
        connection.commit()
        try:
            with ThreadPoolExecutor(1) as pool:
                assert pool.submit(sync, world).result(timeout=10).status == "busy"
            assert world[4].requests == []
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})
            connection.commit()


def test_keyset_pagination_scope_and_stale_coverage(world):
    world[4].pages["fill"] = {None: [fill("f3"), fill("f2"), fill("f1")], "f1": []}
    sync(world)
    first = page(world, limit=2)
    assert [i.trade_id for i in first.items] == ["f3", "f2"] and first.next_cursor
    assert [i.trade_id for i in page(world, limit=2, cursor=first.next_cursor).items] == ["f1"]
    with Session(world[0]) as session:
        with pytest.raises(ValidationAppError):
            read_activity(
                session,
                scope=ActivityScope(uuid4(), world[3].account_uid),
                binding=credential_binding(world[1]),
                kind="fill",
                cursor=first.next_cursor,
            )
        with pytest.raises(ValidationAppError):
            read_activity(
                session,
                scope=world[3],
                binding=credential_binding(world[1]),
                kind="order",
                cursor=first.next_cursor,
            )
        stale = read_activity(
            session,
            scope=world[3],
            binding=credential_binding(world[1]),
            kind="fill",
            now=NOW + timedelta(minutes=6),
        )
        assert stale.freshness == "stale" and stale.coverage[1].last_successful_sync == NOW


def test_pagination_loop_stops_with_old_cursor_intact(world):
    world[4].pages["fill"]["f1"] = [fill("f1")]
    assert sync(world).error_code == "native_identity_conflict"
    assert page(world).coverage[1].native_cursor == "f1"


def test_disabled_and_shutdown_before_send_have_no_io(world):
    disabled = world[2].model_copy(update={"enabled": False})
    assert run_activity_sync(world[0], world[1], disabled).status == "disabled"
    assert sync(world, shutdown=lambda: True).status == "interrupted"
    assert world[4].requests == []


def test_authenticated_api_pins_organization_and_validates_cursor(world):
    sync(world)
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    tenant = TenantContext(
        uuid4(), world[3].organization_id, "reader@example.test", MembershipRole.VIEWER
    )

    def session_dependency():
        with Session(world[0]) as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_settings] = lambda: world[1]
    app.dependency_overrides[get_activity_settings] = lambda: world[2]
    with TestClient(app) as client:
        assert client.get("/exchange/blofin/activity").status_code == 401
        app.dependency_overrides[get_current_tenant] = lambda: tenant
        result = client.get("/exchange/blofin/activity")
        assert (
            result.status_code == 200
            and result.json()["items"][0]["quantity"] == "0.025000000000000000"
        )
        assert client.get("/exchange/blofin/activity?cursor=not-base64").status_code == 422
        assert client.get("/exchange/blofin/activity?limit=101").status_code == 422
        app.dependency_overrides[get_current_tenant] = lambda: TenantContext(
            tenant.user_id, uuid4(), tenant.email, tenant.membership_role
        )
        assert client.get("/exchange/blofin/activity").status_code == 404
        assert client.post("/exchange/blofin/activity").status_code == 405


def test_verified_alphatrade_echo_matches_once_without_simulator_projection(world):
    """A real manual command through a simulated venue, then native account history."""
    from decimal import Decimal

    import httpx

    from app.core.config import Environment, Settings
    from app.db.models import (
        ExecutionAccount,
        ExecutionCommand,
        ExecutionFillFact,
        Membership,
        User,
        VenueSubmitEffect,
    )
    from app.providers.exchange.blofin_client import BloFinClient
    from app.providers.exchange.governed_blofin import GovernedBloFinDemoProvider
    from app.schemas.manual_demo import ManualDemoConfirmation, ManualDemoPreviewRequest
    from app.services.manual_demo_service import ManualDemoService
    from tests.support.phase5_market import EVALUATED_AT
    from tests.test_manual_blofin_demo import ManualVenue

    tenant = TenantContext(
        uuid4(), world[3].organization_id, "manual@example.test", MembershipRole.OWNER
    )
    account_id = uuid4()
    with Session(world[0]) as session:
        session.add(User(id=tenant.user_id, email=tenant.email, hashed_password="fixture"))
        session.flush()
        session.add(
            Membership(
                organization_id=tenant.organization_id,
                user_id=tenant.user_id,
                role=MembershipRole.OWNER,
            )
        )
        session.add(
            ExecutionAccount(
                id=account_id,
                organization_id=tenant.organization_id,
                user_id=tenant.user_id,
                name="Fixture account",
                execution_mode="PAPER",
                account_mode="NET",
                enabled=True,
            )
        )
        session.commit()
    execution_settings = Settings(
        _env_file=None,
        environment="local",
        execution_mode="paper",
        provider_mode="mock",
        exchange_mode="paper_exchange_demo",
        blofin_demo_enabled=True,
        manual_blofin_demo_enabled=True,
        governed_blofin_demo_enabled=False,
        enable_real_trading=False,
        global_kill_switch_active=False,
        blofin_api_key="fixture",
        blofin_api_secret="fixture",
        blofin_api_passphrase="fixture",
        blofin_demo_rest_base_url="https://demo-trading-openapi.blofin.com",
        governed_blofin_demo_organization_id=str(tenant.organization_id),
        governed_blofin_demo_user_id=str(tenant.user_id),
        governed_blofin_demo_account_id=str(account_id),
    ).model_copy(
        update={"environment": Environment.STAGING, "perpetual_evidence_source": "binance_usdm"}
    )
    execution_venue = ManualVenue(Decimal("100000"))
    execution_provider = GovernedBloFinDemoProvider(
        BloFinClient(
            base_url=execution_settings.blofin_demo_rest_base_url,
            api_key="fixture",
            api_secret="fixture",
            api_passphrase="fixture",
            transport=httpx.MockTransport(execution_venue.handle),
            sleeper=lambda _: None,
            max_retries=0,
        ),
        clock=lambda: EVALUATED_AT,
    )
    with Session(world[0]) as session:
        service = ManualDemoService(
            session, execution_settings, provider=execution_provider, clock=lambda: EVALUATED_AT
        )
        preview = service.preview(
            tenant,
            ManualDemoPreviewRequest(side="BUY", quantity="2", stop="99000", target="102000"),
        )
        result = service.confirm(
            tenant,
            ManualDemoConfirmation(
                revision_id=preview.revision_id,
                content_hash=preview.content_hash,
                confirm=True,
                label="manual demo test",
            ),
        )
        command_id = result.command_id
        client_id = session.scalar(
            select(VenueSubmitEffect.client_order_id).where(
                VenueSubmitEffect.command_id == command_id
            )
        )
        local_fills_before = session.scalar(select(func.count()).select_from(ExecutionFillFact))
        commands_before = session.scalar(select(func.count()).select_from(ExecutionCommand))
    assert client_id and execution_venue.post_count == 1
    world[4].pages["order"] = {
        None: [
            order("o2", clientOrderId="looksAlphaTradeButUnverified"),
            order("o1", clientOrderId=client_id),
        ],
        "o1": [],
    }
    world[4].pages["fill"] = {
        None: [fill("f3", "o2"), fill("f2", "o1"), fill("f1", "o1")],
        "f1": [],
    }
    assert sync(world).status == "bounded"
    result = page(world)
    assert len(result.items) == 3
    matched = [i for i in result.items if i.origin == "alphatrade_matched"]
    assert len(matched) == 2 and all(i.command_id == command_id for i in matched)
    assert all(i.strategy_id is None for i in result.items)
    assert result.items[0].origin == "native" and result.items[0].command_id is None
    sync(world)
    assert len(page(world).items) == 3
    with Session(world[0]) as session:
        assert (
            session.scalar(select(func.count()).select_from(ExecutionFillFact))
            == local_fills_before
        )
        assert session.scalar(select(func.count()).select_from(ExecutionCommand)) == commands_before


def test_missed_window_gap_is_explicit(world):
    sync(world)
    # After an outage longer than the lookback, coverage must retain an explicit gap.
    later = NOW + timedelta(days=9)
    for kind in ("order", "fill"):
        world[4].pages[kind] = {None: []}
    assert (
        run_activity_sync(
            world[0], world[1], world[2], provider=world[4].provider(), clock=lambda: later
        ).status
        == "bounded"
    )
    with Session(world[0]) as session:
        result = read_activity(
            session, scope=world[3], binding=credential_binding(world[1]), kind="fill", now=later
        )
        assert all(c.gap_detected for c in result.coverage)
        assert result.partial_coverage


def test_repository_cannot_advance_another_account_checkpoint(world):
    from app.repositories.blofin_activity import ActivityConflictError, BloFinActivityRepository

    sync(world)
    with Session(world[0]) as session:
        checkpoint = session.get(BloFinActivityCursor, (*world[3].key(), "fill"))
        other_repo = BloFinActivityRepository(
            session, ActivityScope(world[3].organization_id, "other")
        )
        previous = (checkpoint.native_cursor, checkpoint.window_complete)
        with pytest.raises(ActivityConflictError):
            other_repo.persist_page(checkpoint, (), {}, NOW)
        assert (checkpoint.native_cursor, checkpoint.window_complete) == previous


def test_organization_scopes_do_not_share_facts_or_checkpoints(world):
    engine, settings, config, scope, venue = world
    sync(world)
    other_org = uuid4()
    with Session(engine) as session:
        session.add(Organization(id=other_org, name="Another activity organization"))
        session.commit()
    other_config = config.model_copy(update={"organization_id": other_org, "max_pages": 1})
    assert (
        run_activity_sync(
            engine, settings, other_config, provider=venue.provider(), clock=lambda: NOW
        ).pages_committed
        == 1
    )
    with Session(engine) as session:
        other_page = read_activity(
            session,
            scope=ActivityScope(other_org, scope.account_uid),
            binding=credential_binding(settings),
            kind="fill",
            now=NOW,
        )
        assert other_page.items == [] and other_page.coverage[1].last_successful_sync is None
        assert (
            len(
                read_activity(
                    session, scope=scope, binding=credential_binding(settings), kind="fill", now=NOW
                ).items
            )
            == 1
        )


def test_invalid_page_shape_preserves_previous_success_and_marks_stale(world):
    sync(world)
    world[4].pages["fill"][None] = {"unexpected": "object"}
    assert sync(world).error_code == "provider_unavailable"
    result = page(world)
    assert len(result.items) == 1 and result.freshness == "stale"
    assert result.coverage[1].last_successful_sync == NOW
