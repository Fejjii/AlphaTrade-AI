"""Real PostgreSQL registration races and authenticated tenant-scoped HTTP proof."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    AuditLog,
    EmailVerificationToken,
    ExecutionAccount,
    Membership,
    Organization,
    RefreshToken,
    User,
)
from app.db.session import get_session
from app.main import create_app
from app.repositories.audit import AuditRepository
from app.schemas.common import ActorType, AuditEventType, MembershipRole
from app.security.tenant import TenantContext
from app.services.automated_paper_loop import _paper_account
from app.services.execution_account_service import ExecutionAccountService
from app.workers.watcher_paper_targets import PaperScanTarget
from tests.support.postgres_persistence import POSTGRES_URL, requires_postgres

pytestmark = requires_postgres
PATH = "/execution/accounts/paper"


@pytest.fixture
def factory():
    # Only identity/auth/audit tables, in a unique disposable PostgreSQL schema.
    assert make_url(POSTGRES_URL).database == "alphatrade_test"
    engine = create_engine(POSTGRES_URL)
    schema = f"execution_account_test_{uuid4().hex}"
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    scoped = engine.execution_options(schema_translate_map={None: schema})
    tables = [
        Organization.__table__,
        User.__table__,
        Membership.__table__,
        ExecutionAccount.__table__,
        AuditLog.__table__,
        RefreshToken.__table__,
        EmailVerificationToken.__table__,
    ]
    Base.metadata.create_all(scoped, tables=tables)
    yield sessionmaker(scoped, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(DropSchema(schema, cascade=True))
    engine.dispose()


@pytest.fixture
def client(factory):
    settings = Settings(
        _env_file=None,
        environment="local",
        execution_mode="paper",
        enable_real_trading=False,
        governed_blofin_demo_enabled=False,
        provider_mode="mock",
        access_token_denylist_use_redis=False,
        rate_limit_use_redis=False,
        market_data_cache_use_redis=False,
        jwt_secret="paper-account-test-secret-at-least-32-characters",
        require_email_verified=False,
    )
    app = create_app(settings=settings)

    def session_override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def register_owner(client, email="owner@example.com"):
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "test-secure-password-123",
            "organization_name": email,
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    headers = {"Authorization": f"Bearer {data['tokens']['access_token']}"}
    return headers, UUID(data["organization"]["id"]), UUID(data["user"]["id"])


def tenant_seed(factory):
    tenant = TenantContext(uuid4(), uuid4(), "owner@example.com", MembershipRole.OWNER)
    with factory() as session:
        session.add(Organization(id=tenant.organization_id, name="Test tenant"))
        session.add(User(id=tenant.user_id, email=tenant.email, hashed_password="unused"))
        session.flush()
        session.add(
            Membership(
                organization_id=tenant.organization_id,
                user_id=tenant.user_id,
                role=MembershipRole.OWNER,
            )
        )
        session.commit()
    return tenant


def test_concurrent_setup_and_replay_preserve_one_identity_and_one_audit(factory):
    tenant = tenant_seed(factory)
    barrier = threading.Barrier(4)

    def setup(index):
        with factory() as session:
            barrier.wait(timeout=10)
            result = ExecutionAccountService(session).register(
                tenant, request_id=f"race-{index}", trace_id=f"race-{index}"
            )
            session.commit()
            return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(setup, range(4)))
    assert len({result.account.id for result in results}) == 1
    assert sum(result.created for result in results) == 1
    with factory() as session:
        replay = ExecutionAccountService(session).register(
            tenant, request_id="retry", trace_id="retry"
        )
        session.commit()
        assert not replay.created and replay.account.id == results[0].account.id
        assert session.scalar(select(func.count()).select_from(ExecutionAccount)) == 1
        audit = session.scalars(select(AuditLog)).one()
        assert audit.action == AuditEventType.EXECUTION_ACCOUNT_REGISTERED
        assert audit.actor_type == ActorType.USER
        assert (audit.organization_id, audit.user_id) == (tenant.organization_id, tenant.user_id)
        assert audit.resource_id == str(replay.account.id)
        assert audit.redacted_metadata == {"execution_mode": "PAPER", "account_mode": "NET"}


def test_status_then_setup_and_replay_are_authenticated_and_durable(client, factory):
    assert client.get(PATH).status_code == 401
    assert client.post(PATH, json={}).status_code == 401
    headers, organization_id, user_id = register_owner(client)
    assert client.get(PATH, headers=headers).json() == {"account": None, "can_register": True}
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ExecutionAccount)) == 0
    first = client.post(PATH, headers=headers, json={})
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["created"] is True
    assert result["account"]["execution_mode"] == "PAPER"
    assert result["account"]["account_mode"] == "NET"
    account_id = UUID(result["account"]["id"])
    assert client.get(PATH, headers=headers).json()["account"] == result["account"]
    repeated = client.post(PATH, headers=headers, json={}).json()
    assert repeated == {"account": result["account"], "created": False}
    with factory() as session:
        account = session.get(ExecutionAccount, account_id)
        assert (account.organization_id, account.user_id) == (organization_id, user_id)
        # Only identity/auth/audit tables exist: setup does not need credentials,
        # strategy, risk, permission, plan, authorization or dispatch persistence.
        assert session.scalar(select(func.count()).select_from(ExecutionAccount)) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"organization_id": str(uuid4())},
        {"user_id": str(uuid4())},
        {"account_id": str(uuid4())},
        {"execution_mode": "REAL"},
        {"execution_mode": "PAPER"},
        {"account_mode": "HEDGE"},
        {"enabled": True},
        {"name": "reset account"},
    ],
)
def test_setup_rejects_client_identity_modes_or_mutation_fields(client, factory, body):
    headers, _, _ = register_owner(client)
    response = client.post(PATH, headers=headers, json=body)
    assert response.status_code == 422, response.text
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ExecutionAccount)) == 0


@pytest.mark.parametrize("role", [MembershipRole.TRADER, MembershipRole.VIEWER])
def test_non_owner_cannot_register(client, factory, role):
    headers, organization_id, user_id = register_owner(client)
    with factory() as session:
        membership = session.scalars(
            select(Membership).where(
                Membership.organization_id == organization_id, Membership.user_id == user_id
            )
        ).one()
        membership.role = role
        session.commit()
    assert client.get(PATH, headers=headers).json() == {"account": None, "can_register": False}
    assert client.post(PATH, headers=headers, json={}).status_code == 403


@pytest.mark.parametrize("ambiguous", [False, True])
def test_disabled_or_ambiguous_accounts_are_not_replaced_or_reenabled(client, factory, ambiguous):
    headers, organization_id, user_id = register_owner(client)
    with factory() as session:
        for index in range(2 if ambiguous else 1):
            session.add(
                ExecutionAccount(
                    organization_id=organization_id,
                    user_id=user_id,
                    name=f"Existing {index}",
                    enabled=ambiguous,
                )
            )
        session.commit()
    code = "execution_account_ambiguous" if ambiguous else "execution_account_disabled"
    for response in (
        client.get(PATH, headers=headers),
        client.post(PATH, headers=headers, json={}),
    ):
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == code
    with factory() as session:
        accounts = session.scalars(select(ExecutionAccount)).all()
        assert len(accounts) == (2 if ambiguous else 1)
        assert all(account.enabled == ambiguous for account in accounts)
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == AuditEventType.EXECUTION_ACCOUNT_REGISTERED)
            )
            == 0
        )


def test_valid_existing_account_uuid_and_properties_are_preserved(client, factory):
    headers, organization_id, user_id = register_owner(client)
    account_id = uuid4()
    with factory() as session:
        session.add(
            ExecutionAccount(
                id=account_id,
                organization_id=organization_id,
                user_id=user_id,
                name="Previously governed account",
            )
        )
        session.commit()
    result = client.post(PATH, headers=headers, json={}).json()
    assert result["created"] is False
    assert result["account"]["id"] == str(account_id)
    assert result["account"]["name"] == "Previously governed account"


def test_registration_isolates_both_organization_and_owner(client, factory):
    first_headers, first_org, first_user = register_owner(client)
    second_headers, second_org, second_user = register_owner(client, "second@example.com")
    first = client.post(PATH, headers=first_headers, json={}).json()["account"]
    assert client.get(PATH, headers=second_headers).json()["account"] is None
    # A different owner's disabled account in the same org must not contaminate
    # the current owner scope or cause a foreign account UUID to be reused.
    with factory() as session:
        session.add(
            ExecutionAccount(
                organization_id=second_org,
                user_id=first_user,
                name="Different owner",
                enabled=False,
            )
        )
        session.add(
            ExecutionAccount(
                organization_id=first_org, user_id=second_user, name="Different org", enabled=False
            )
        )
        session.commit()
    second = client.post(PATH, headers=second_headers, json={}).json()["account"]
    assert second["id"] != first["id"]
    assert client.get(PATH, headers=first_headers).json()["account"]["id"] == first["id"]


def test_audit_failure_rolls_back_registration(client, factory, monkeypatch):
    headers, _, _ = register_owner(client)

    def fail_audit(self, row):
        raise RuntimeError("Simulated audit storage failure")

    monkeypatch.setattr(AuditRepository, "add", fail_audit)
    response = client.post(PATH, headers=headers, json={})
    assert response.status_code == 500
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ExecutionAccount)) == 0


def test_registered_uuid_resolves_for_canonical_paper_continuation(factory):
    tenant = tenant_seed(factory)
    target = PaperScanTarget(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        strategy_id=uuid4(),
        strategy_version_id=uuid4(),
        compiled_setup_definition_id=uuid4(),
        compiled_content_hash="a" * 64,
        fusion_policy_version="test/v1",
        symbol="BTCUSDT",
    )
    with factory() as session:
        assert _paper_account(session, target) is None
        registered = ExecutionAccountService(session).register(
            tenant, request_id="canonical", trace_id="canonical"
        )
        session.commit()
    with factory() as session:
        assert _paper_account(session, target).id == registered.account.id
