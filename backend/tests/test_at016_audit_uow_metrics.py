"""AT-016 — audit/usage unit-of-work hardening + gated RED metrics."""

from __future__ import annotations

import re
import threading
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.models import AuditLog, Organization, User
from app.db.models import UsageEvent as UsageEventModel
from app.main import create_app
from app.observability.metrics import (
    normalize_route,
    observe_request,
    status_class,
)
from app.schemas.audit import AuditRecordCreate
from app.schemas.common import (
    ActorType,
    AuditEventType,
    AuditResult,
    AuditSeverity,
)
from app.schemas.usage import UsageEventCreate
from app.services.audit_service import AuditPersistenceError, AuditService
from app.services.usage_service import UsagePersistenceError, UsageService


@pytest.fixture
def engine_factory(tmp_path: object) -> Iterator[tuple[object, sessionmaker[Session]]]:
    # File-backed SQLite so isolated sessions use separate connections/transactions.
    from pathlib import Path

    db_path = Path(str(tmp_path)) / "at016_uow.sqlite"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn: object, _record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield engine, factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(engine_factory: tuple[object, sessionmaker[Session]]) -> Iterator[Session]:
    _engine, factory = engine_factory
    with factory() as session:
        org = Organization(name="AT016 Org")
        user = User(email="at016@test.local", hashed_password="hash")
        session.add_all([org, user])
        session.commit()  # release write lock so durable_isolated can use another connection
        session.info["org_id"] = org.id
        session.info["user_id"] = user.id
        session.info["factory"] = factory
        yield session


def test_record_flushes_without_commit(db_session: Session) -> None:
    factory: sessionmaker[Session] = db_session.info["factory"]
    audit = AuditService(db_session, session_factory=factory)
    with patch.object(db_session, "commit", wraps=db_session.commit) as commit_spy:
        record = audit.record(
            AuditRecordCreate(
                request_id="uow-1",
                trace_id="uow-1",
                event_type=AuditEventType.PAPER_ORDER_CREATED,
                resource_type="paper_order",
                result=AuditResult.SUCCESS,
            )
        )
    assert record is not None
    assert record.event_id is not None
    assert db_session.get(AuditLog, record.event_id) is not None
    commit_spy.assert_not_called()
    db_session.rollback()
    assert db_session.get(AuditLog, record.event_id) is None
    # Durable only after an explicit caller commit.
    record2 = audit.record(
        AuditRecordCreate(
            request_id="uow-1b",
            trace_id="uow-1b",
            event_type=AuditEventType.PAPER_ORDER_CREATED,
            resource_type="paper_order",
            result=AuditResult.SUCCESS,
        )
    )
    assert record2 is not None
    db_session.commit()
    with factory() as other:
        assert other.get(AuditLog, record2.event_id) is not None


def test_business_and_audit_commit_together(db_session: Session) -> None:
    factory: sessionmaker[Session] = db_session.info["factory"]
    audit = AuditService(db_session, session_factory=factory)
    org = Organization(name="Txn Org")
    db_session.add(org)
    record = audit.record(
        AuditRecordCreate(
            request_id="uow-2",
            trace_id="uow-2",
            event_type=AuditEventType.PROPOSAL_CREATED,
            resource_type="proposal",
            organization_id=None,
            result=AuditResult.SUCCESS,
        )
    )
    assert record is not None
    db_session.commit()
    with factory() as other:
        assert other.get(Organization, org.id) is not None
        assert other.get(AuditLog, record.event_id) is not None


def test_business_failure_rolls_back_audit_and_usage(db_session: Session) -> None:
    factory: sessionmaker[Session] = db_session.info["factory"]
    audit = AuditService(db_session, session_factory=factory)
    usage = UsageService(db_session)
    audit.record(
        AuditRecordCreate(
            request_id="uow-3",
            trace_id="uow-3",
            event_type=AuditEventType.PAPER_ORDER_CREATED,
            resource_type="paper_order",
            result=AuditResult.SUCCESS,
        )
    )
    usage.record(
        UsageEventCreate(
            request_id="uow-3",
            feature="paper_execution",
            provider="paper-engine",
            input_tokens=0,
            output_tokens=0,
        )
    )
    db_session.rollback()
    with factory() as other:
        assert list(other.scalars(select(AuditLog)).all()) == []
        assert list(other.scalars(select(UsageEventModel)).all()) == []


def test_nonstrict_audit_failure_preserves_flushed_business(db_session: Session) -> None:
    factory: sessionmaker[Session] = db_session.info["factory"]
    audit = AuditService(db_session, strict_mode=False, session_factory=factory)
    org = Organization(name="Keep Org")
    db_session.add(org)
    db_session.flush()
    with patch.object(audit._repo, "add", side_effect=RuntimeError("audit boom")):
        record = audit.record(
            AuditRecordCreate(
                request_id="uow-4a",
                trace_id="uow-4a",
                event_type=AuditEventType.PAPER_ORDER_CREATED,
                resource_type="paper_order",
                result=AuditResult.SUCCESS,
            )
        )
    assert record is not None
    db_session.commit()
    with factory() as other:
        assert other.get(Organization, org.id) is not None


def test_strict_audit_failure_raises_without_silent_success(db_session: Session) -> None:
    factory: sessionmaker[Session] = db_session.info["factory"]
    audit = AuditService(db_session, strict_mode=True, session_factory=factory)
    org = Organization(name="Strict Org")
    db_session.add(org)
    db_session.flush()
    with (
        patch.object(audit._repo, "add", side_effect=RuntimeError("audit boom")),
        pytest.raises(AuditPersistenceError),
    ):
        audit.record(
            AuditRecordCreate(
                request_id="uow-4",
                trace_id="uow-4",
                event_type=AuditEventType.PAPER_ORDER_CREATED,
                resource_type="paper_order",
                result=AuditResult.SUCCESS,
            )
        )
    # Savepoint rolled back audit only; business still pending for caller decision.
    db_session.commit()
    with factory() as other:
        assert other.get(Organization, org.id) is not None


def test_usage_fail_open_unless_strict(db_session: Session) -> None:
    usage = UsageService(db_session, strict_mode=False)
    with patch.object(usage._repo, "add", side_effect=RuntimeError("usage boom")):
        event = usage.record(
            UsageEventCreate(
                request_id="uow-5",
                feature="agent_chat",
                provider="mock",
                input_tokens=1,
                output_tokens=1,
            )
        )
    assert event.usage_event_id is not None
    usage_strict = UsageService(db_session, strict_mode=True)
    with (
        patch.object(usage_strict._repo, "add", side_effect=RuntimeError("usage boom")),
        pytest.raises(UsagePersistenceError),
    ):
        usage_strict.record(
            UsageEventCreate(
                request_id="uow-5b",
                feature="agent_chat",
                provider="mock",
                input_tokens=1,
                output_tokens=1,
            )
        )


def test_no_hidden_commit_on_record(db_session: Session) -> None:
    audit = AuditService(db_session, session_factory=db_session.info["factory"])
    usage = UsageService(db_session)
    with (
        patch.object(db_session, "commit", wraps=db_session.commit) as commit_spy,
    ):
        audit.record(
            AuditRecordCreate(
                request_id="uow-6",
                trace_id="uow-6",
                event_type=AuditEventType.RISK_BLOCK,
                resource_type="proposal",
                result=AuditResult.BLOCKED,
            )
        )
        usage.record(
            UsageEventCreate(
                request_id="uow-6",
                feature="agent_chat",
                provider="mock",
                input_tokens=0,
                output_tokens=0,
            )
        )
    commit_spy.assert_not_called()


def test_audit_event_id_available_after_flush(db_session: Session) -> None:
    audit = AuditService(db_session, session_factory=db_session.info["factory"])
    record = audit.record(
        AuditRecordCreate(
            request_id="uow-7",
            trace_id="uow-7",
            event_type=AuditEventType.APPROVAL_DECISION,
            resource_type="approval",
            result=AuditResult.SUCCESS,
        )
    )
    assert record is not None
    row = db_session.get(AuditLog, record.event_id)
    assert row is not None
    assert row.id == record.event_id


def test_durable_isolated_survives_business_rollback(db_session: Session) -> None:
    factory: sessionmaker[Session] = db_session.info["factory"]
    audit = AuditService(db_session, session_factory=factory)
    # Commit durable event first (no open write txn) — mirrors reject/security paths
    # that audit then raise without pending business writes.
    durable = audit.record_durable_isolated(
        AuditRecordCreate(
            request_id="uow-8",
            trace_id="uow-8",
            event_type=AuditEventType.QUOTA_BLOCK,
            resource_type="organization_quota",
            result=AuditResult.BLOCKED,
            severity=AuditSeverity.HIGH,
            actor_type=ActorType.SYSTEM,
        )
    )
    assert durable is not None
    org = Organization(name="Rollback Org")
    db_session.add(org)
    db_session.flush()
    db_session.rollback()
    with factory() as other:
        assert other.get(Organization, org.id) is None
        assert other.get(AuditLog, durable.event_id) is not None


def test_durable_isolated_does_not_commit_request_session(db_session: Session) -> None:
    factory: sessionmaker[Session] = db_session.info["factory"]
    audit = AuditService(db_session, session_factory=factory)
    with patch.object(db_session, "commit", wraps=db_session.commit) as commit_spy:
        durable = audit.record_durable_isolated(
            AuditRecordCreate(
                request_id="uow-9",
                trace_id="uow-9",
                event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
                resource_type="rate_limit",
                result=AuditResult.BLOCKED,
                actor_type=ActorType.SYSTEM,
            )
        )
    assert durable is not None
    commit_spy.assert_not_called()
    with factory() as other:
        assert other.get(AuditLog, durable.event_id) is not None


def test_metrics_disabled_by_default(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 404


def test_metrics_requires_token_outside_local() -> None:
    with pytest.raises(ValidationError, match="metrics_scrape_token"):
        Settings(
            environment="staging",
            jwt_secret="x" * 32,
            database_url="postgresql+psycopg://user:pass@db.example.com:5432/alphatrade",
            redis_url="redis://redis.example.com:6379/0",
            qdrant_url="https://qdrant.example.com",
            openai_api_key="sk-test-not-a-real-key",
            cors_origins="https://app.example.com",
            auth_refresh_cookie_enabled=True,
            auth_cookie_secure=True,
            auth_cookie_samesite="none",
            enable_real_trading=False,
            execution_mode="paper",
            provider_mode="fallback",
            rate_limit_use_redis=True,
            debug=False,
            log_json=False,
            metrics_enabled=True,
            metrics_scrape_token="",
        )


def test_metrics_scrape_and_labels() -> None:
    settings = Settings(
        environment="local",
        debug=True,
        log_json=False,
        execution_mode="paper",
        enable_real_trading=False,
        rate_limit_use_redis=False,
        market_data_cache_use_redis=False,
        access_token_denylist_use_redis=False,
        provider_mode="mock",
        market_data_provider="mock",
        metrics_enabled=True,
        metrics_scrape_token="test-scrape-token",
    )
    app = create_app(settings=settings)
    with TestClient(app) as client:
        denied = client.get("/metrics")
        assert denied.status_code == 401
        ok = client.get(
            "/metrics",
            headers={"Authorization": "Bearer test-scrape-token"},
        )
        assert ok.status_code == 200
        body = ok.text
        assert "http_requests_total" in body
        # Hit a real route then scrape again.
        health = client.get("/health")
        assert health.status_code == 200
        scraped = client.get(
            "/metrics",
            headers={"Authorization": "Bearer test-scrape-token"},
        )
        assert scraped.status_code == 200
        assert 'route="/health"' in scraped.text or "route=" in scraped.text
        assert "status_class=" in scraped.text
        # No high-cardinality leakage.
        assert "?" not in scraped.text
        assert "sk-" not in scraped.text
        assert not re.search(r"organization_id|user_id|request_id=", scraped.text)


def test_status_class_and_route_normalization() -> None:
    assert status_class(200) == "2xx"
    assert status_class(404) == "4xx"
    assert status_class(503) == "5xx"
    request = MagicMock()
    request.scope = {"route": MagicMock(path="/execution/orders/{order_id}")}
    request.url.path = "/execution/orders/11111111-1111-1111-1111-111111111111?x=1"
    assert normalize_route(request) == "/execution/orders/{order_id}"
    request.scope = {"route": None}
    request.url.path = "/foo/22222222-2222-2222-2222-222222222222/bar"
    assert normalize_route(request) == "unmatched"


def test_metrics_concurrent_safe() -> None:
    errors: list[BaseException] = []

    def _worker() -> None:
        try:
            for _ in range(50):
                observe_request(
                    method="GET",
                    route="/health",
                    status_code=200,
                    duration_seconds=0.001,
                )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


def test_paper_defaults_unchanged() -> None:
    settings = Settings(log_json=False)
    assert settings.execution_mode == "paper"
    assert settings.enable_real_trading is False
    assert settings.metrics_enabled is False
