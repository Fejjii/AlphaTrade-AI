"""Approved target projection and bounded historical repair on real PostgreSQL."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.errors import JournalProjectionConflictError
from app.db.models import AuditLog, JournalLifecycleEvent, JournalProjectionReceipt, JournalTrade
from app.db.models import TradePlanRevision as PlanRow
from app.schemas.execution_protocol import ClosePaperPlanRequest
from app.services import canonical_paper_execution
from app.services.audit_service import AuditService
from app.services.canonical_execution_journal import (
    canonical_planned_targets,
    journal_planned_targets,
)
from app.services.journal_lifecycle_projector import JournalLifecycleProjector
from tests.support.phase8_runtime import EXECUTE_AT, prepared_authorized_canonical
from tests.support.postgres_persistence import phase7_plan_session_factory, requires_postgres
from tests.test_phase8_canonical_paper_execution import _execute

pytestmark = requires_postgres


def _snapshot(session):
    return {
        model.__name__: sorted(
            [
                {
                    column.key: deepcopy(getattr(row, column.key))
                    for column in model.__table__.columns
                }
                for row in session.scalars(select(model))
            ],
            key=lambda row: str(row["id"]),
        )
        for model in (JournalLifecycleEvent, JournalProjectionReceipt, PlanRow)
    }


def _scope(trade):
    return {
        "organization_id": trade.organization_id,
        "user_id": trade.user_id,
        "account_id": trade.account_id,
        "journal_trade_id": trade.id,
        "revision_id": trade.trade_plan_revision_id,
    }


def _repair_audits(session):
    return list(
        session.scalars(select(AuditLog).where(AuditLog.request_id == "journal-target-repair"))
    )


@pytest.fixture
def historical(monkeypatch):
    factory = phase7_plan_session_factory()
    _world, envelope, authorization = prepared_authorized_canonical(factory)
    original = canonical_paper_execution._instrument_payload

    def omitted_targets(plan):
        payload = original(plan)
        payload.pop("planned_targets", None)
        return payload

    with monkeypatch.context() as old:
        old.setattr(canonical_paper_execution, "_instrument_payload", omitted_targets)
        result, session, service, _runtime = _execute(
            factory, envelope, authorization, key="historical-targets"
        )
        try:
            service.apply_paper_plan_fill(
                command_id=result.command_id,
                fill_quantity=Decimal("1"),
                fill_price=Decimal("100000"),
                source_identity="historical-fill",
                occurred_at=EXECUTE_AT,
            )
            session.commit()
            trade = session.scalars(select(JournalTrade)).one()
            assert trade.planned_targets == []  # Exact pre-fix omission, no history rewritten.
            scope = _scope(trade)
            snapshot = _snapshot(session)
        finally:
            session.close()
    return factory, envelope, authorization, result, scope, snapshot


@pytest.mark.parametrize("fill_first", [False, True])
def test_new_approval_fill_and_close_preserve_approved_targets(monkeypatch, fill_first):
    factory = phase7_plan_session_factory()
    _world, envelope, authorization = prepared_authorized_canonical(factory)
    expected = journal_planned_targets(envelope.plan)
    assert expected
    if fill_first:
        # Governed demo creates Journal only after a verified fill, not at approval.
        monkeypatch.setattr(
            canonical_paper_execution.CanonicalPaperExecutionService,
            "_project_approved_plan",
            lambda *args: None,
        )
    result, session, service, _runtime = _execute(
        factory, envelope, authorization, key="new-targets"
    )
    try:
        if fill_first:
            assert session.scalar(select(JournalTrade)) is None
        else:
            assert session.scalars(select(JournalTrade)).one().planned_targets == expected
        service.apply_paper_plan_fill(
            command_id=result.command_id,
            fill_quantity=Decimal("1"),
            fill_price=Decimal("100000"),
            source_identity="new-fill",
            occurred_at=EXECUTE_AT,
        )
        session.commit()
        assert session.scalars(select(JournalTrade)).one().planned_targets == expected
        for event in session.scalars(select(JournalLifecycleEvent)):
            assert event.payload["planned_targets"] == canonical_planned_targets(envelope.plan)
        service.close_canonical_paper_plan(
            ClosePaperPlanRequest(
                organization_id=envelope.plan.organization_id,
                user_id=envelope.plan.user_id,
                account_id=envelope.plan.account_id,
                revision_id=envelope.plan.revision_id,
                command_id=result.command_id,
                exit_price=Decimal("101000"),
                exit_reason="target-reached",
                occurred_at=EXECUTE_AT,
                idempotency_key="targets-close",
            )
        )
        session.commit()
        assert session.scalars(select(JournalTrade)).one().planned_targets == expected
    finally:
        session.close()


def test_mapping_preserves_known_price_order_and_unallocated_runner(historical):
    _factory, envelope, *_rest = historical
    template = envelope.plan.risk_and_exits.targets[0]
    first = template.model_copy(
        update={
            "order": 1,
            "price": template.price.model_copy(update={"value": Decimal("84714.10")}),
            "quantity_fraction": Decimal("0.50"),
        }
    )
    second = template.model_copy(
        update={
            "order": 2,
            "price": template.price.model_copy(update={"value": Decimal("86000.25")}),
            "quantity_fraction": Decimal("0.25"),
        }
    )
    plan = envelope.plan.model_copy(
        update={
            "risk_and_exits": envelope.plan.risk_and_exits.model_copy(
                update={
                    "targets": (first, second),
                    "runner": envelope.plan.risk_and_exits.runner.model_copy(
                        update={
                            "enabled": True,
                            "activation_target_order": 2,
                            "remaining_quantity_fraction": Decimal("0.25"),
                        }
                    ),
                }
            )
        }
    )
    assert journal_planned_targets(plan) == [
        {"price": "84714.10", "size_fraction": 0.5, "label": "TP1"},
        {"price": "86000.25", "size_fraction": 0.25, "label": "TP2"},
    ]
    assert canonical_planned_targets(plan) == [
        {"price": "84714.10", "size_fraction": "0.50", "label": "TP1"},
        {"price": "86000.25", "size_fraction": "0.25", "label": "TP2"},
    ]
    single = plan.model_copy(
        update={
            "risk_and_exits": plan.risk_and_exits.model_copy(
                update={"targets": (first.model_copy(update={"quantity_fraction": Decimal("1")}),)}
            )
        }
    )
    assert journal_planned_targets(single) == [
        {"price": "84714.10", "size_fraction": 1.0, "label": "TP1"}
    ]


def test_historical_replay_dry_run_repair_and_restart_preserve_hashes(historical):
    factory, envelope, authorization, original, scope, snapshot = historical
    replay, session, service, _runtime = _execute(
        factory, envelope, authorization, key="historical-targets"
    )
    try:
        assert replay.replayed and replay.command_id == original.command_id
        fill = service.apply_paper_plan_fill(
            command_id=original.command_id,
            fill_quantity=Decimal("1"),
            fill_price=Decimal("100000"),
            source_identity="historical-fill",
            occurred_at=EXECUTE_AT,
        )
        assert fill.replayed
        session.commit()
        trade = session.get(JournalTrade, scope["journal_trade_id"])
        before = {
            column.key: deepcopy(getattr(trade, column.key))
            for column in JournalTrade.__table__.columns
        }
        projector = JournalLifecycleProjector(session, AuditService(session))
        preview = projector.repair_planned_targets(**scope)
        assert preview["status"] == "would_repair" and preview["dry_run"] is True
        assert trade.planned_targets == [] and not _repair_audits(session)
        assert _snapshot(session) == snapshot
        applied = projector.repair_planned_targets(**scope, dry_run=False)
        assert applied["status"] == "repaired"
        session.commit()
        assert trade.planned_targets == journal_planned_targets(envelope.plan)
        for key, value in before.items():
            if key not in {"planned_targets", "projector_lock_version", "updated_at"}:
                assert getattr(trade, key) == value
        assert trade.projector_lock_version == before["projector_lock_version"] + 1
        audits = _repair_audits(session)
        assert len(audits) == 1
        assert audits[0].organization_id == scope["organization_id"]
        assert audits[0].user_id == scope["user_id"]
        assert audits[0].resource_id == str(scope["journal_trade_id"])
        assert audits[0].redacted_metadata == {
            "action": "repair_planned_targets",
            "account_id": str(scope["account_id"]),
            "execution_lifecycle_id": str(original.command_id),
            "revision_id": str(scope["revision_id"]),
            "plan_content_hash": envelope.plan.content_hash,
            "before": [],
            "after": journal_planned_targets(envelope.plan),
        }
        assert _snapshot(session) == snapshot
    finally:
        session.close()
    replay, session, service, _runtime = _execute(
        factory, envelope, authorization, key="historical-targets"
    )
    try:
        assert replay.replayed
        service.apply_paper_plan_fill(
            command_id=original.command_id,
            fill_quantity=Decimal("1"),
            fill_price=Decimal("100000"),
            source_identity="historical-fill",
            occurred_at=EXECUTE_AT,
        )
        result = JournalLifecycleProjector(session, AuditService(session)).repair_planned_targets(
            **scope, dry_run=False
        )
        session.commit()
        assert result["status"] == "already_correct"
        assert len(_repair_audits(session)) == 1
        assert _snapshot(session) == snapshot
    finally:
        session.close()


@pytest.mark.parametrize(
    "field", ["organization_id", "user_id", "account_id", "revision_id", "journal_trade_id"]
)
@pytest.mark.parametrize("dry_run", [True, False])
def test_repair_refuses_wrong_scope_or_plan_without_changes(historical, field, dry_run):
    factory, _envelope, _authorization, _result, scope, snapshot = historical
    invalid = {**scope, field: uuid4()}
    with factory() as session:
        with pytest.raises(JournalProjectionConflictError):
            JournalLifecycleProjector(session, AuditService(session)).repair_planned_targets(
                **invalid, dry_run=dry_run
            )
        session.rollback()
        assert session.get(JournalTrade, scope["journal_trade_id"]).planned_targets == []
        assert not _repair_audits(session)
        assert _snapshot(session) == snapshot


@pytest.mark.parametrize("defect", ["conflicting_targets", "candidate_id", "evidence_window_hash"])
def test_repair_refuses_conflicting_projection_or_lineage(historical, defect):
    factory, _envelope, _authorization, _result, scope, snapshot = historical
    with factory() as session:
        trade = session.get(JournalTrade, scope["journal_trade_id"])
        if defect == "conflicting_targets":
            trade.planned_targets = [{"price": "1", "size_fraction": 1.0, "label": "TP1"}]
        else:
            setattr(trade, defect, uuid4() if defect == "candidate_id" else "f" * 64)
        session.commit()
        with pytest.raises(JournalProjectionConflictError):
            JournalLifecycleProjector(session, AuditService(session)).repair_planned_targets(
                **scope, dry_run=False
            )
        session.rollback()
        assert not _repair_audits(session)
        assert _snapshot(session) == snapshot


def test_concurrent_repair_converges_with_one_audit(historical):
    factory, envelope, _authorization, _result, scope, snapshot = historical
    barrier = Barrier(2)

    def repair():
        with factory() as session:
            barrier.wait(timeout=10)
            result = JournalLifecycleProjector(
                session, AuditService(session)
            ).repair_planned_targets(**scope, dry_run=False)
            session.commit()
            return result["status"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(repair) for _ in range(2)]
        assert sorted(f.result(timeout=20) for f in futures) == ["already_correct", "repaired"]
    with factory() as session:
        assert session.get(
            JournalTrade, scope["journal_trade_id"]
        ).planned_targets == journal_planned_targets(envelope.plan)
        assert len(_repair_audits(session)) == 1
        assert _snapshot(session) == snapshot


def test_audit_failure_leaves_projection_unchanged(historical, monkeypatch):
    factory, _envelope, _authorization, _result, scope, snapshot = historical

    def fail(self, record):
        assert self._strict_mode is True
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditService, "record", fail)
    with factory() as session:
        with pytest.raises(RuntimeError, match="audit unavailable"):
            JournalLifecycleProjector(session, AuditService(session)).repair_planned_targets(
                **scope, dry_run=False
            )
        session.rollback()
        assert session.get(JournalTrade, scope["journal_trade_id"]).planned_targets == []
        assert _snapshot(session) == snapshot
