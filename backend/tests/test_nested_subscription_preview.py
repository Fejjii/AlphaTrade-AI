"""Authenticated read-only baseline preview and explicit draft scope creation."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import (
    ApprovalAuthorization,
    AuditLog,
    CompiledSetupDefinition,
    UserStrategy,
    UserStrategyVersion,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import Timeframe
from app.schemas.nested_continuation import NestedContinuationSpec
from app.services.compiled_setup_service import CompiledSetupService
from app.strategy_brain.nested_preview import NESTED_DEMO_MARKETS, preview_nested_subscriptions
from app.strategy_brain.service import create_template
from tests.support.postgres_persistence import phase7_plan_session_factory, requires_postgres
from tests.test_execution_account_registration import register_owner

pytestmark = requires_postgres
PATH = "/strategy-brain/templates/nested/preview"


@pytest.fixture
def context():
    factory = phase7_plan_session_factory()
    settings = Settings(
        _env_file=None,
        environment="local",
        execution_mode="paper",
        enable_real_trading=False,
        provider_mode="mock",
        access_token_denylist_use_redis=False,
        rate_limit_use_redis=False,
        market_data_cache_use_redis=False,
        jwt_secret="preview-test-secret-at-least-32-characters",
        require_email_verified=False,
    )
    app = create_app(settings=settings)

    def session_override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    with TestClient(app, raise_server_exceptions=False) as client:
        headers, org, user = register_owner(client)
        with factory() as session:
            template = create_template(
                session,
                organization_id=org,
                user_id=user,
                spec=NestedContinuationSpec(
                    symbol="BTCUSDT", parameters={"minimum_impulse": "0.007"}
                ),
            )
            session.commit()
        yield factory, client, headers, org, user, template


def counts(session):
    return tuple(
        session.scalar(select(func.count()).select_from(model))
        for model in (
            UserStrategy,
            UserStrategyVersion,
            CompiledSetupDefinition,
            ApprovalAuthorization,
            AuditLog,
        )
    )


def test_preview_is_stable_exact_and_does_not_create_or_approve(context):
    factory, client, headers, _org, _user, template = context
    with factory() as session:
        before = counts(session)
    body = {"baseline_version_id": str(template["version_id"])}
    first = client.post(PATH, headers=headers, json=body)
    assert first.status_code == 200, first.text
    preview = first.json()
    assert client.post(PATH, headers=headers, json=body).json() == preview
    assert preview["subscription_count"] == 10
    assert not preview["changes_active_rules"] and not preview["execution_authorized"]
    assert {(p["spec"]["symbol"], p["spec"]["direction"]) for p in preview["additions"]} == {
        (symbol, direction) for symbol in NESTED_DEMO_MARKETS for direction in ("long", "short")
    }
    for addition in preview["additions"]:
        assert addition["spec"]["parameters"]["minimum_impulse"] == "0.007"
        assert addition["spec"]["trigger_timeframe"] == "15m"
        assert addition["spec"]["parameters"]["provisional"]
        assert addition["requires_explicit_approval"]
        assert addition["instrument_availability"] == "unverified"
    assert sum(p["action"] == "reuse_existing" for p in preview["additions"]) == 1
    with factory() as session:
        assert counts(session) == before


def test_explicit_creation_reuses_each_exact_draft_and_keeps_preview_hash(context):
    factory, client, headers, _org, _user, template = context
    body = {"baseline_version_id": str(template["version_id"])}
    before = client.post(PATH, headers=headers, json=body).json()
    ids = set()
    for addition in before["additions"]:
        first = client.post(
            "/strategy-brain/templates/nested", headers=headers, json=addition["spec"]
        )
        assert first.status_code == 201, first.text
        repeated = client.post(
            "/strategy-brain/templates/nested", headers=headers, json=addition["spec"]
        )
        assert repeated.json()["version_id"] == first.json()["version_id"]
        assert first.json()["lifecycle"] == "draft"
        ids.add(first.json()["version_id"])
    assert len(ids) == 10
    after = client.post(PATH, headers=headers, json=body).json()
    assert after["preview_hash"] == before["preview_hash"]
    assert all(
        p["action"] == "reuse_existing" and p["requires_explicit_approval"]
        for p in after["additions"]
    )
    with factory() as session:
        assert counts(session)[:4] == (10, 10, 0, 0)


def test_only_existing_exact_approved_version_is_marked_approved(context):
    factory, _client, _headers, org, user, template = context
    with factory() as session:
        compiled = CompiledSetupService(session)
        compiled.compile_version(template["version_id"], organization_id=org, user_id=user)
        compiled.approve_version(
            template["version_id"], organization_id=org, user_id=user, confirm_message="I confirm"
        )
        session.commit()
        before = counts(session)
        result = preview_nested_subscriptions(
            session, organization_id=org, user_id=user, baseline_version_id=template["version_id"]
        )
        assert counts(session) == before
        approved = [p for p in result["additions"] if p["existing_version_approved"]]
        assert len(approved) == 1 and approved[0]["existing_version_id"] == str(
            template["version_id"]
        )
        assert sum(p["requires_explicit_approval"] for p in result["additions"]) == 9
        assert not result["execution_authorized"]


def test_authentication_and_tenant_scope(context):
    factory, client, headers, org, user, template = context
    body = {"baseline_version_id": str(template["version_id"])}
    assert client.post(PATH, json=body).status_code == 401
    other_headers, _, _ = register_owner(client, email="other@example.com")
    assert client.post(PATH, headers=other_headers, json=body).status_code == 404
    assert (
        client.post(
            PATH, headers=headers, json={**body, "organization_id": str(org), "user_id": str(user)}
        ).status_code
        == 422
    )
    assert (
        client.post(PATH, headers=headers, json={"baseline_version_id": str(uuid4())}).status_code
        == 404
    )
    with factory() as session, pytest.raises(NotFoundError):
        preview_nested_subscriptions(
            session,
            organization_id=org,
            user_id=uuid4(),
            baseline_version_id=template["version_id"],
        )


def test_changed_selected_version_is_a_conflict_without_overwriting_history(context):
    factory, _client, _headers, org, user, template = context
    with factory() as session:
        original = session.get(UserStrategyVersion, template["version_id"])
        changed = NestedContinuationSpec.model_validate(original.pattern_spec)
        changed = changed.model_copy(
            update={"parameters": changed.parameters.model_copy(update={"confirmation_window": 12})}
        )
        strategy = session.get(UserStrategy, original.strategy_id)
        replacement = UserStrategyVersion(
            strategy_id=strategy.id,
            version=2,
            card=original.card,
            pattern_spec=changed.model_dump(mode="json"),
        )
        session.add(replacement)
        strategy.current_version = 2
        session.commit()
        result = preview_nested_subscriptions(
            session, organization_id=org, user_id=user, baseline_version_id=original.id
        )
        conflicts = [p for p in result["additions"] if p["action"] == "name_conflict"]
        assert len(conflicts) == 1
        assert conflicts[0]["existing_version_id"] is None
        assert conflicts[0]["requires_explicit_approval"]
        assert session.get(UserStrategyVersion, original.id).pattern_spec == original.pattern_spec
        assert session.get(UserStrategy, strategy.id).current_version == 2


@pytest.mark.parametrize("invalid", ["timeframe", "sfp"])
def test_preview_refuses_non_15m_or_non_nested_baseline(context, invalid):
    factory, _client, _headers, org, user, _template = context
    with factory() as session:
        if invalid == "timeframe":
            spec = NestedContinuationSpec(symbol="BTCUSDT", trigger_timeframe=Timeframe.H1)
        else:
            from tests.test_sfp_detector import spec as sfp_spec

            spec = sfp_spec()
        source = create_template(session, organization_id=org, user_id=user, spec=spec)
        session.commit()
        with pytest.raises(ValidationAppError):
            preview_nested_subscriptions(
                session, organization_id=org, user_id=user, baseline_version_id=source["version_id"]
            )


def test_explicit_approved_versions_yield_ten_independent_bounded_targets(context):
    from app.workers.watcher_paper_targets import list_watchlist_scan_targets

    factory, _client, _headers, org, user, template = context
    with factory() as session:
        preview = preview_nested_subscriptions(
            session, organization_id=org, user_id=user, baseline_version_id=template["version_id"]
        )
        for addition in preview["additions"]:
            created = create_template(
                session,
                organization_id=org,
                user_id=user,
                spec=NestedContinuationSpec.model_validate(addition["spec"]),
            )
            compiled = CompiledSetupService(session)
            compiled.compile_version(created["version_id"], organization_id=org, user_id=user)
            compiled.approve_version(
                created["version_id"],
                organization_id=org,
                user_id=user,
                confirm_message="I confirm",
            )
        session.commit()
        targets = list_watchlist_scan_targets(
            session, symbols=NESTED_DEMO_MARKETS, organization_id=org, limit=20
        )
        assert len(targets) == 10
        assert len({t.strategy_id for t in targets}) == 10
        assert len({t.policy_id for t in targets}) == 10
        assert all(sum(t.symbol == symbol for t in targets) == 2 for symbol in NESTED_DEMO_MARKETS)
        assert all(t.timeframe == "15m" and t.user_id == user for t in targets)
        assert (
            len(
                list_watchlist_scan_targets(
                    session, symbols=NESTED_DEMO_MARKETS, organization_id=org, limit=3
                )
            )
            == 3
        )
        assert (
            list_watchlist_scan_targets(
                session, symbols=NESTED_DEMO_MARKETS, organization_id=uuid4(), limit=20
            )
            == ()
        )
