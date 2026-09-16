"""Shared Wave 1B plan/authorization helpers for Phase 1 slices 7-10 tests."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    ExchangeAccount,
    ExecutionAccount,
    Organization,
    PaperValidationAlert,
    PaperValidationCandidate,
    PaperValidationDraft,
    SetupDefinition,
    User,
    UserStrategy,
    UserStrategyVersion,
)
from app.db.models import TradePlanRevision as TradePlanRevisionModel
from app.db.models import TradeProposal as TradeProposalModel
from app.schemas.approval import ApprovalAuthorization, ApprovalDecisionRequest
from app.schemas.common import (
    ApprovalAction,
    ExchangeAccountStatus,
    PaperAlertType,
    RiskSeverity,
    SetupCategory,
    StrategyId,
)
from app.schemas.execution_protocol import ExecutePaperPlanRequest
from app.schemas.proposal import ExitCriteria, TakeProfitLevel, TradeProposalCreate
from app.schemas.trade_plan import (
    AccountMode,
    ExecutionMode,
    TradePlanRevision,
    TradePlanRevisionCreate,
    TradePlanRevisionSemantic,
)
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.canonical_serialization import canonical_sha256
from app.services.execution_service import ExecutionService
from app.services.mappers.trade_plan_mapper import trade_plan_revision_to_schema
from app.services.proposal_service import ProposalService

NOW = datetime(2026, 9, 15, 14, 0, tzinfo=UTC)
CORRELATION_ID = uuid.UUID("09000000-0000-0000-0000-000000000001")
EXECUTE_AT = NOW + timedelta(minutes=2)


def sqlite_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_conn: object, _record: object) -> None:
        # Disable pysqlite autocommit so SAVEPOINT release cannot commit the claim txn.
        dbapi_conn.isolation_level = None  # type: ignore[attr-defined]
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _begin(conn: object) -> None:
        conn.exec_driver_sql("BEGIN")  # type: ignore[attr-defined]

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        yield db
    engine.dispose()


def paper_settings(
    *,
    database_url: str,
    global_kill_switch_active: bool = False,
) -> Settings:
    return Settings(
        environment="local",
        log_json=False,
        execution_mode="paper",
        enable_real_trading=False,
        exchange_mode="paper_internal",
        provider_mode="mock",
        market_data_provider="mock",
        database_url=database_url,
        jwt_secret="phase1-slices-7-10-secret-32b-min",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
        metrics_enabled=False,
        global_kill_switch_active=global_kill_switch_active,
    )


def execution_service(
    session: Session,
    *,
    database_url: str = "sqlite+pysqlite:///:memory:",
    global_kill_switch_active: bool = False,
) -> ExecutionService:
    return ExecutionService(
        session,
        paper_settings(
            database_url=database_url,
            global_kill_switch_active=global_kill_switch_active,
        ),
        AuditService(session),
    )


def seed_support(session: Session) -> dict[str, Any]:
    organization = Organization(name=f"P1 {uuid.uuid4()}")
    other_organization = Organization(name=f"Other {uuid.uuid4()}")
    user = User(email=f"plan-{uuid.uuid4()}@example.com", hashed_password="not-a-real-hash")
    other_user = User(email=f"other-{uuid.uuid4()}@example.com", hashed_password="not-a-real-hash")
    session.add_all([organization, other_organization, user, other_user])
    session.flush()
    strategy = UserStrategy(
        organization_id=organization.id,
        user_id=user.id,
        name="Phase 1 strategy",
        setup_type=StrategyId.HTF_TREND_PULLBACK,
    )
    session.add(strategy)
    session.flush()
    strategy_version = UserStrategyVersion(
        strategy_id=strategy.id,
        version=1,
        card={"strategy_name": "Phase 1"},
    )
    setup = SetupDefinition(
        name=f"Phase 1 setup {uuid.uuid4()}",
        strategy_id=StrategyId.HTF_TREND_PULLBACK,
        category=SetupCategory.TREND,
        version=1,
    )
    session.add_all([strategy_version, setup])
    session.flush()
    alert = PaperValidationAlert(
        organization_id=organization.id,
        user_id=user.id,
        alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
        message="Complete deterministic evidence is available.",
    )
    session.add(alert)
    session.flush()
    draft = PaperValidationDraft(
        organization_id=organization.id,
        source_alert_id=alert.id,
        symbol="BTCUSDT",
        timeframe="4h",
        direction="long",
        review_status="approved",
        created_by=user.id,
        status="ready",
    )
    session.add(draft)
    session.flush()
    candidate = PaperValidationCandidate(
        organization_id=organization.id,
        draft_id=draft.id,
        source_alert_id=alert.id,
        symbol="BTCUSDT",
        timeframe="4h",
        direction="long",
        created_by=user.id,
        strategy_id=strategy.id,
        strategy_version_id=strategy_version.id,
    )
    account_one = ExecutionAccount(
        organization_id=organization.id,
        user_id=user.id,
        name="Primary paper account",
        execution_mode=ExecutionMode.PAPER,
        account_mode=AccountMode.NET,
    )
    account_two = ExecutionAccount(
        organization_id=organization.id,
        user_id=user.id,
        name="Secondary paper account",
        execution_mode=ExecutionMode.PAPER,
        account_mode=AccountMode.NET,
    )
    other_account = ExecutionAccount(
        organization_id=organization.id,
        user_id=other_user.id,
        name="Other principal paper account",
        execution_mode=ExecutionMode.PAPER,
        account_mode=AccountMode.NET,
    )
    exchange_account = ExchangeAccount(
        organization_id=organization.id,
        user_id=user.id,
        exchange="blofin",
        api_key_ref="secret-store://demo-key",
        has_withdrawal_permission=False,
        status=ExchangeAccountStatus.ACTIVE,
    )
    session.add_all([candidate, account_one, account_two, other_account, exchange_account])
    session.flush()
    proposal = ProposalService(session, AuditService(session)).create(
        TradeProposalCreate(
            organization_id=organization.id,
            user_id=user.id,
            strategy_id=StrategyId.HTF_TREND_PULLBACK,
            user_strategy_id=strategy.id,
            symbol="BTCUSDT",
            timeframe="4h",
            direction="long",
            entry_price=Decimal("100"),
            position_size=Decimal("2"),
            leverage=Decimal("2"),
            exit=ExitCriteria(
                invalidation="Close below the exact stop.",
                stop_loss=Decimal("95"),
                take_profits=[
                    TakeProfitLevel(price=Decimal("110"), size_fraction=0.5),
                    TakeProfitLevel(price=Decimal("120"), size_fraction=0.5),
                ],
            ),
            confidence=0.8,
            risk_level=RiskSeverity.MEDIUM,
            rationale="Complete deterministic test plan.",
            approval_required=True,
        )
    )
    session.flush()
    return {
        "organization": organization,
        "other_organization": other_organization,
        "user": user,
        "other_user": other_user,
        "strategy_version": strategy_version,
        "setup": setup,
        "candidate": candidate,
        "account_one": account_one,
        "account_two": account_two,
        "other_account": other_account,
        "exchange_account": exchange_account,
        "proposal_id": proposal.id,
        "correlation_id": CORRELATION_ID,
    }


def plan_request(ids: dict[str, Any], **updates: Any) -> TradePlanRevisionCreate:
    payload: dict[str, Any] = {
        "account_id": ids["account_one"].id,
        "exchange_account_id": ids["exchange_account"].id,
        "strategy_version_id": ids["strategy_version"].id,
        "setup_definition_id": ids["setup"].id,
        "candidate_id": ids["candidate"].id,
        "permission_attestation_id": uuid.UUID("10000000-0000-0000-0000-000000000001"),
        "permission_attestation_version": "blofin-demo-permissions-v1",
        "evidence_ids": [
            uuid.UUID("20000000-0000-0000-0000-000000000001"),
            uuid.UUID("20000000-0000-0000-0000-000000000002"),
        ],
        "evidence_venue": "BINANCE",
        "evidence_market": "PERPETUAL",
        "evidence_instrument": "BTC-USDT-PERP",
        "evidence_observed_at": NOW - timedelta(seconds=30),
        "evidence_freshness_seconds": 60,
        "evidence_is_live": True,
        "evidence_fallback_used": False,
        "evidence_sequence_complete": True,
        "evidence_final": True,
        "execution_venue": "BLOFIN_DEMO",
        "execution_market": "PERPETUAL",
        "execution_instrument": "BTC-USDT",
        "timeframe": "4h",
        "instrument_mapping_version": "blofin-btc-usdt-v1",
        "side": "BUY",
        "quantity": {"value": "2.000", "unit": "CONTRACTS"},
        "quantity_unit": "CONTRACTS",
        "order_type": "MARKET",
        "time_in_force": "IOC",
        "limit_price": None,
        "market_marker": True,
        "entry_zone": {"lower": "99.50", "upper": "100.50", "price_unit": "USDT"},
        "entry_zone_derivation": {
            "formula_id": "pattern-trigger-intersection",
            "formula_version": "1",
        },
        "slippage_policy": {
            "policy_id": "conservative-entry",
            "policy_version": "1",
            "maximum_bps": "15.0",
        },
        "reduce_only": False,
        "margin_mode": "CROSS",
        "position_mode": "NET",
        "instrument_rules": {
            "contract_multiplier": "1",
            "contract_type": "LINEAR",
            "base_currency": "BTC",
            "quote_currency": "USDT",
            "settlement_currency": "USDT",
            "tick_size": "0.10",
            "lot_size": "1",
            "minimum_quantity": "1",
            "minimum_notional": "5",
            "rules_version": "blofin-rules-2026-09-15",
        },
        "basis_policy": {
            "policy_id": "cross-venue-basis",
            "policy_version": "1",
            "evidence_price": {"value": "100.00", "unit": "USDT"},
            "execution_price": {"value": "100.10", "unit": "USDT"},
            "formula": "(execution_price-evidence_price)/evidence_price",
            "timestamp": NOW - timedelta(seconds=20),
            "tolerance_bps": "20",
            "freshness_seconds": 60,
        },
        "risk_and_exits": {
            "risk_budget": {"value": "10", "unit": "USDT"},
            "maximum_loss": {"value": "12", "unit": "USDT"},
            "fee_allowance": {"value": "1", "unit": "USDT"},
            "funding_allowance": {"value": "0.25", "unit": "USDT"},
            "slippage_allowance": {"value": "0.75", "unit": "USDT"},
            "stop": {"value": "95", "unit": "USDT"},
            "targets": [
                {
                    "order": 1,
                    "price": {"value": "110", "unit": "USDT"},
                    "quantity_fraction": "0.50",
                    "derivation": {"formula_id": "nearest-structure", "formula_version": "1"},
                },
                {
                    "order": 2,
                    "price": {"value": "120", "unit": "USDT"},
                    "quantity_fraction": "0.25",
                    "derivation": {"formula_id": "next-structure", "formula_version": "1"},
                },
            ],
            "runner": {
                "enabled": True,
                "activation_target_order": 2,
                "remaining_quantity_fraction": "0.25",
                "rule_id": "atr-trailing-runner",
                "rule_version": "1",
                "expression": "trail_by_atr_after_target_2",
            },
            "leverage": "2",
            "margin_assumption_id": "cross-margin-conservative",
            "margin_assumption_version": "1",
        },
        "valid_from": NOW,
        "valid_until": NOW + timedelta(hours=1),
        "calculation_inputs": [
            {
                "name": "rounded_contract_quantity",
                "input_value": "2.000",
                "result_value": "2",
                "unit": "CONTRACTS",
                "formula_id": "floor-to-lot",
                "formula_version": "1",
                "precision": 0,
                "rounding_mode": "ROUND_FLOOR",
                "conservative_remainder": "0",
            }
        ],
        "execution_policy_version": "paper-entry-policy-v1",
        "presentation_metadata": {"channel": "WEB", "display_title": "BTC setup"},
    }
    payload.update(updates)
    return TradePlanRevisionCreate.model_validate(payload)


def persist_plan(
    session: Session,
    ids: dict[str, Any],
    request: TradePlanRevisionCreate | None = None,
) -> TradePlanRevision:
    data = request or plan_request(ids)
    semantic = TradePlanRevisionSemantic(
        plan_id=ids["proposal_id"],
        revision_id=uuid.uuid4(),
        organization_id=ids["organization"].id,
        user_id=ids["user"].id,
        **data.semantic_terms(),
    )
    row = TradePlanRevisionModel(
        id=semantic.revision_id,
        plan_id=semantic.plan_id,
        organization_id=semantic.organization_id,
        user_id=semantic.user_id,
        account_id=semantic.account_id,
        exchange_account_id=semantic.exchange_account_id,
        schema_version=semantic.schema_version,
        operation=semantic.operation,
        strategy_version_id=semantic.strategy_version_id,
        setup_definition_id=semantic.setup_definition_id,
        candidate_id=semantic.candidate_id,
        expected_account_mode=semantic.expected_account_mode,
        permission_attestation_id=semantic.permission_attestation_id,
        permission_attestation_version=semantic.permission_attestation_version,
        execution_venue=semantic.execution_venue,
        execution_instrument=semantic.execution_instrument,
        execution_policy_version=semantic.execution_policy_version,
        valid_from=semantic.valid_from,
        valid_until=semantic.valid_until,
        semantic_payload=semantic.model_dump(mode="json"),
        correlation_id=ids["correlation_id"],
        content_hash=canonical_sha256(semantic),
        presentation_metadata=data.presentation_metadata.model_dump(mode="json"),
    )
    proposal = session.get(TradeProposalModel, ids["proposal_id"])
    assert proposal is not None
    session.add(row)
    proposal.latest_plan_revision_id = row.id
    session.flush()
    return trade_plan_revision_to_schema(row)


def approve_plan(
    session: Session,
    ids: dict[str, Any],
    plan: TradePlanRevision,
    *,
    clock: datetime = NOW + timedelta(minutes=1),
) -> ApprovalAuthorization:
    service = ApprovalService(session, AuditService(session), clock=lambda: clock)
    approval = service.create_for_plan_revision(
        revision_id=plan.revision_id,
        organization_id=plan.organization_id,
        user_id=plan.user_id,
    )
    decided = service.decide(
        approval.id,
        ApprovalDecisionRequest(action=ApprovalAction.APPROVE),
        principal_organization_id=plan.organization_id,
        principal_user_id=plan.user_id,
    )
    assert decided.authorization is not None
    return decided.authorization


def execute_request(
    ids: dict[str, Any],
    plan: TradePlanRevision,
    authorization: ApprovalAuthorization,
    *,
    key: str,
    user_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
) -> ExecutePaperPlanRequest:
    return ExecutePaperPlanRequest(
        organization_id=ids["organization"].id,
        user_id=user_id or ids["user"].id,
        account_id=account_id or plan.account_id,
        authorization_id=authorization.authorization_id,
        revision_id=plan.revision_id,
        idempotency_key=key,
    )


def prepared_authorized_plan(
    session: Session,
    **plan_updates: Any,
) -> tuple[dict[str, Any], TradePlanRevision, ApprovalAuthorization]:
    ids = seed_support(session)
    plan = persist_plan(session, ids, plan_request(ids, **plan_updates))
    authorization = approve_plan(session, ids, plan)
    session.flush()
    return ids, plan, authorization


@pytest.fixture
def session() -> Iterator[Session]:
    yield from sqlite_session()
