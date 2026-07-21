"""AT-012: fail-closed fresh risk evaluation at paper order placement."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.errors import TradingPolicyError
from app.db.base import Base
from app.db.models import DailyRiskState, Membership, Organization, Position, User, UserRiskSettings
from app.schemas.approval import ApprovalDecisionRequest
from app.schemas.common import (
    ApprovalAction,
    MembershipRole,
    RiskAction,
    RiskRuleId,
    RiskSeverity,
    StrategyId,
)
from app.schemas.execution import PaperOrderRequest
from app.schemas.proposal import ExitCriteria, TakeProfitLevel, TradeProposalCreate
from app.schemas.risk import KillSwitchMutationRequest, RiskCheckResult, TriggeredRule
from app.security.passwords import hash_password
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.execution_service import ExecutionService
from app.services.proposal_service import ProposalService
from app.services.risk.kill_switch import KillSwitchService
from app.services.risk.settings_service import RiskSettingsService

ORG_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a3")

# 0.005 * 60000 = 300 notional; 5% of 10000 equity = 500 → ALLOW
_SIZE = Decimal("0.005")
_ENTRY = Decimal("60000")
_STOP = Decimal("58000")


@pytest.fixture
def at012_db() -> Iterator[tuple[sessionmaker[Session], Settings]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn: object, _record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(
        environment="local",
        log_json=False,
        execution_mode="paper",
        enable_real_trading=False,
        exchange_mode="paper_internal",
        provider_mode="mock",
        market_data_provider="mock",
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="at012-paper-risk-secret-32-bytes-min",
        rate_limit_use_redis=False,
        access_token_denylist_use_redis=False,
    )
    with factory() as session:
        session.add(Organization(id=ORG_ID, name="AT012 Org"))
        session.add(
            User(
                id=USER_ID,
                email="at012@test.example",
                hashed_password=hash_password("TestPassword123!", settings),
            )
        )
        session.flush()
        session.add(
            Membership(
                user_id=USER_ID,
                organization_id=ORG_ID,
                role=MembershipRole.OWNER,
            )
        )
        session.commit()
    yield factory, settings
    engine.dispose()


def _exit(*, stop: Decimal = _STOP) -> ExitCriteria:
    return ExitCriteria(
        invalidation="Close below stop.",
        stop_loss=stop,
        take_profits=[TakeProfitLevel(price=Decimal("62000"), size_fraction=0.5)],
    )


def _allow_risk() -> RiskCheckResult:
    return RiskCheckResult(
        action=RiskAction.ALLOW,
        severity=RiskSeverity.LOW,
        explanation="seed allow",
        approval_required=True,
    )


def _seed(
    session: Session,
    *,
    risk_result: RiskCheckResult | None = None,
    stop: Decimal = _STOP,
    size: Decimal = _SIZE,
    include_risk: bool = True,
) -> tuple[uuid.UUID, uuid.UUID]:
    audit = AuditService(session)
    proposals = ProposalService(session, audit)
    approvals = ApprovalService(session, audit)
    kwargs: dict[str, Any] = {
        "organization_id": ORG_ID,
        "user_id": USER_ID,
        "strategy_id": StrategyId.HTF_TREND_PULLBACK,
        "symbol": "BTCUSDT",
        "timeframe": "4h",
        "direction": "long",
        "entry_price": _ENTRY,
        "position_size": size,
        "leverage": Decimal("3"),
        "exit": _exit(stop=stop),
        "confidence": 0.7,
        "risk_level": RiskSeverity.MEDIUM,
        "rationale": "at012",
        "approval_required": True,
    }
    if include_risk:
        kwargs["risk_result"] = risk_result if risk_result is not None else _allow_risk()
    proposal = proposals.create(TradeProposalCreate(**kwargs))
    approval = approvals.create_for_proposal(
        proposal_id=proposal.id,  # type: ignore[arg-type]
        organization_id=ORG_ID,
        user_id=USER_ID,
        risk_level=proposal.risk_level,
        confidence=float(proposal.confidence),
    )
    approvals.decide(approval.id, ApprovalDecisionRequest(action=ApprovalAction.APPROVE))
    session.commit()
    return proposal.id, approval.id  # type: ignore[return-value]


def _execution(session: Session, settings: Settings, **kwargs: object) -> ExecutionService:
    return ExecutionService(
        session,
        settings,
        AuditService(session),
        risk_settings=RiskSettingsService(session, AuditService(session)),
        **kwargs,  # type: ignore[arg-type]
    )


def _request(
    proposal_id: uuid.UUID,
    approval_id: uuid.UUID,
    *,
    symbol: str = "BTCUSDT",
    side: str = "buy",
    size: Decimal = _SIZE,
    price: Decimal | None = None,
    key: str = "at012-key",
) -> PaperOrderRequest:
    return PaperOrderRequest(
        proposal_id=proposal_id,
        approval_id=approval_id,
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        type="market",
        size=size,
        price=price,
        idempotency_key=key,
    )


def test_valid_fresh_risk_allows_paper_placement(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = at012_db
    with factory() as session:
        pid, aid = _seed(session)
        order = _execution(session, settings).place_paper_order(_request(pid, aid))
        session.commit()
        assert order.mode.value == "paper"
        assert order.size == _SIZE
        assert order.price == _ENTRY


def test_missing_risk_result_blocked(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = at012_db
    with factory() as session:
        pid, aid = _seed(session, include_risk=False)
        with pytest.raises(TradingPolicyError) as exc:
            _execution(session, settings).place_paper_order(_request(pid, aid, key="miss-risk"))
        assert exc.value.details.get("reason") == "missing_risk_result"


def test_stale_stored_block_still_blocked(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = at012_db
    blocked = RiskCheckResult(
        action=RiskAction.BLOCK,
        severity=RiskSeverity.HIGH,
        triggered_rules=[
            TriggeredRule(
                rule_id=RiskRuleId.NO_STOP_LOSS,
                action=RiskAction.BLOCK,
                severity=RiskSeverity.HIGH,
                message="stop",
            )
        ],
        explanation="blocked",
        approval_required=False,
    )
    with factory() as session:
        # Proposal has stop so fresh eval might ALLOW — stored BLOCK must still refuse.
        pid, aid = _seed(session, risk_result=blocked)
        with pytest.raises(TradingPolicyError) as exc:
            _execution(session, settings).place_paper_order(_request(pid, aid, key="stale-blk"))
        # Eligibility short-circuits on stored BLOCK before fresh re-eval.
        assert exc.value.details.get("reason") in {
            "stale_risk_blocked",
            "fresh_risk_blocked",
            "eligibility_blocked",
        }


def test_zero_stop_distance_blocked(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = at012_db
    with factory() as session:
        pid, aid = _seed(session, stop=_ENTRY)
        with pytest.raises(TradingPolicyError) as exc:
            _execution(session, settings).place_paper_order(_request(pid, aid, key="zero-stop"))
        assert exc.value.details.get("reason") == "invalid_stop_distance"


def test_missing_stop_blocked(at012_db: tuple[sessionmaker[Session], Settings]) -> None:
    """Gate rejects when ORM stop_loss is missing (DB NOT NULL; mock ORM attribute)."""
    from datetime import UTC, datetime
    from unittest.mock import MagicMock, patch

    from app.schemas.approval import ApprovalRequest as ApprovalSchema
    from app.schemas.common import ApprovalStatus
    from app.schemas.proposal import TradeProposal
    from app.services.mappers.proposal_mapper import proposal_to_schema
    from app.services.paper_execution_risk_gate import PaperExecutionRiskGate
    from app.services.risk.daily_risk_accounting import DailyRiskAccounting
    from app.services.risk_service import RiskService

    factory, _settings = at012_db
    with factory() as session:
        pid, aid = _seed(session)
        from app.db.models import TradeProposal as TradeProposalRow

        row = session.get(TradeProposalRow, pid)
        assert row is not None
        schema = proposal_to_schema(row)
        approval = ApprovalSchema(
            id=aid,
            proposal_id=pid,
            organization_id=ORG_ID,
            user_id=USER_ID,
            status=ApprovalStatus.APPROVED,
            risk_level=RiskSeverity.MEDIUM,
            confidence=0.7,
            created_at=datetime.now(UTC),
        )
        mock_proposal = MagicMock()
        mock_proposal.stop_loss = None
        mock_proposal.organization_id = ORG_ID
        mock_proposal.user_id = USER_ID
        mock_proposal.entry_price = _ENTRY
        mock_proposal.position_size = _SIZE
        mock_proposal.leverage = Decimal("3")
        mock_proposal.symbol = "BTCUSDT"
        mock_proposal.strategy_id = StrategyId.HTF_TREND_PULLBACK
        risk_settings = RiskSettingsService(session, AuditService(session))
        gate = PaperExecutionRiskGate(
            risk_service=RiskService(),
            daily_risk=DailyRiskAccounting(session, risk_settings),
            kill_switch=KillSwitchService(session, AuditService(session), _settings),
        )
        with (
            patch(
                "app.services.paper_execution_risk_gate.proposal_to_schema",
                return_value=schema,
            ),
            pytest.raises(TradingPolicyError) as exc,
        ):
            gate.evaluate(
                proposal=mock_proposal,
                approval=approval,
                request=_request(pid, aid, key="nostop-xx"),
            )
        assert exc.value.details.get("reason") == "missing_stop_loss"
        assert isinstance(schema, TradeProposal)


def test_kill_switch_active_blocked(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = at012_db
    with factory() as session:
        KillSwitchService(session, AuditService(session), settings).activate(
            organization_id=ORG_ID,
            actor_user_id=USER_ID,
            payload=KillSwitchMutationRequest(confirm=True, reason="at012 kill test"),
        )
        session.commit()
        pid, aid = _seed(session)
        with pytest.raises(TradingPolicyError) as exc:
            _execution(session, settings).place_paper_order(_request(pid, aid, key="kill-switch"))
        assert exc.value.details.get("reason") in {
            "kill_switch_active",
            "fresh_risk_blocked",
        }


def test_daily_loss_limit_exceeded_blocked(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    """Gate blocks when portfolio-derived realized PnL already breached the limit."""
    from datetime import UTC, datetime

    from app.schemas.common import PositionStatus, TradeDirection

    factory, settings = at012_db
    with factory() as session:
        session.add(
            UserRiskSettings(
                organization_id=ORG_ID,
                user_id=USER_ID,
                daily_loss_limit=Decimal("100"),
                daily_target=None,
                max_trades_per_day=20,
                max_risk_per_trade_percent=Decimal("1"),
                default_account_balance=Decimal("10000"),
                timezone="UTC",
                green_day_protection_enabled=True,
                one_loss_stop_enabled=False,
                overtrading_guard_enabled=True,
            )
        )
        # Authoritative source is closed positions — not a client-writable DailyRiskState row.
        session.add(
            Position(
                organization_id=ORG_ID,
                user_id=USER_ID,
                strategy_id=StrategyId.HTF_TREND_PULLBACK,
                symbol="BTCUSDT",
                direction=TradeDirection.LONG,
                size=_SIZE,
                entry_price=_ENTRY,
                leverage=Decimal("3"),
                stop_loss=_STOP,
                take_profits=[],
                realized_pnl=Decimal("-150"),
                unrealized_pnl=Decimal("0"),
                status=PositionStatus.CLOSED,
                opened_at=datetime.now(UTC),
                closed_at=datetime.now(UTC),
            )
        )
        session.commit()
        pid, aid = _seed(session)
        with pytest.raises(TradingPolicyError) as exc:
            _execution(session, settings).place_paper_order(_request(pid, aid, key="dailyloss"))
        assert exc.value.details.get("reason") == "fresh_risk_blocked"


def test_exposure_size_limit_exceeded_blocked(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = at012_db
    # 0.05 * 60000 = 3000 notional >> 5% of 10000
    oversized = Decimal("0.05")
    with factory() as session:
        pid, aid = _seed(session, size=oversized)
        with pytest.raises(TradingPolicyError) as exc:
            _execution(session, settings).place_paper_order(
                _request(pid, aid, size=oversized, key="exposure")
            )
        assert exc.value.details.get("reason") == "fresh_risk_blocked"
        assert "max_position_size" in str(exc.value.details.get("rules", ""))


def test_modified_client_size_blocked(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = at012_db
    with factory() as session:
        pid, aid = _seed(session, size=_SIZE)
        with pytest.raises(TradingPolicyError) as exc:
            _execution(session, settings).place_paper_order(
                _request(pid, aid, size=Decimal("0.01"), key="size-mis")
            )
        assert exc.value.details.get("reason") == "size_mismatch"


def test_modified_client_price_blocked(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = at012_db
    with factory() as session:
        pid, aid = _seed(session)
        with pytest.raises(TradingPolicyError) as exc:
            _execution(session, settings).place_paper_order(
                _request(pid, aid, price=Decimal("61000"), key="price-mis")
            )
        assert exc.value.details.get("reason") == "price_mismatch"


def test_modified_client_symbol_blocked(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = at012_db
    with factory() as session:
        pid, aid = _seed(session)
        with pytest.raises(TradingPolicyError) as exc:
            _execution(session, settings).place_paper_order(
                _request(pid, aid, symbol="ETHUSDT", key="sym-mism")
            )
        assert exc.value.details.get("reason") == "symbol_mismatch"


def test_modified_client_side_blocked(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = at012_db
    with factory() as session:
        pid, aid = _seed(session)
        with pytest.raises(TradingPolicyError) as exc:
            _execution(session, settings).place_paper_order(
                _request(pid, aid, side="sell", key="side-mism")
            )
        assert exc.value.details.get("reason") == "side_mismatch"


def test_degraded_market_data_refused_when_live_expected(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    factory, settings = at012_db
    settings = settings.model_copy(
        update={"provider_mode": "fallback", "market_data_provider": "binance"}
    )
    mock_md = MagicMock()
    ticker = MagicMock()
    ticker.meta.is_stale = True
    ticker.meta.fallback_used = False
    mock_md.get_ticker.return_value = ticker

    with factory() as session:
        pid, aid = _seed(session)
        with pytest.raises(TradingPolicyError) as exc:
            _execution(session, settings, market_data_service=mock_md).place_paper_order(
                _request(pid, aid, key="stale-md")
            )
        assert exc.value.details.get("reason") == "market_data_degraded"


def test_paper_defaults_unchanged_in_settings(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    _factory, settings = at012_db
    assert settings.execution_mode.value == "paper"
    assert settings.enable_real_trading is False
    assert settings.exchange_mode.value == "paper_internal"


def test_paper_close_uses_server_ticker_when_live_expected(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    """Client exit_price must not control realized PnL when live market data is expected."""
    from app.schemas.common import PositionStatus
    from app.schemas.position import ClosePaperPositionRequest
    from app.services.position_service import PositionService

    factory, settings = at012_db
    settings = settings.model_copy(
        update={"provider_mode": "fallback", "market_data_provider": "binance"}
    )
    mock_md = MagicMock()
    ticker = MagicMock()
    ticker.last_price = Decimal("30000")
    ticker.meta.is_stale = False
    ticker.meta.fallback_used = False
    mock_md.get_ticker.return_value = ticker

    with factory() as session:
        pid, aid = _seed(session)
        _execution(session, settings).place_paper_order(_request(pid, aid, key="close-bind"))
        session.commit()
        position = session.scalar(
            select(Position).where(
                Position.organization_id == ORG_ID,
                Position.status == PositionStatus.OPEN,
            )
        )
        assert position is not None
        # Client claims a winning exit; server ticker forces a losing mark.
        closed = PositionService(
            session,
            AuditService(session),
            settings=settings,
            market_data_service=mock_md,
        ).close_paper(
            position.id,
            ClosePaperPositionRequest(exit_price=Decimal("90000"), reason="claim-win"),
        )
        session.commit()
        assert closed.realized_pnl == Decimal("-150")
        daily = session.scalar(
            select(DailyRiskState).where(DailyRiskState.organization_id == ORG_ID)
        )
        assert daily is not None
        assert daily.realized_pnl == Decimal("-150")


def test_sequential_orders_cannot_bypass_exposure_with_stale_state(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    """First fill updates open exposure; second order at same size must fail closed."""

    factory, settings = at012_db
    # Each order: 0.005 * 60000 = 300 (3% of 10k). Two open → 600 > 5% cap.
    with factory() as session:
        pid1, aid1 = _seed(session)
        first = _execution(session, settings).place_paper_order(
            _request(pid1, aid1, key="seq-ord-1")
        )
        session.commit()
        assert first.size == _SIZE

        daily = session.scalar(
            select(DailyRiskState).where(
                DailyRiskState.organization_id == ORG_ID,
                DailyRiskState.user_id == USER_ID,
            )
        )
        assert daily is not None
        assert daily.trade_count == 1
        assert daily.unrealized_pnl == Decimal("0")
        # Open exposure is recomputed at next evaluate from positions, not client state.

        pid2, aid2 = _seed(session)
        with pytest.raises(TradingPolicyError) as exc:
            _execution(session, settings).place_paper_order(_request(pid2, aid2, key="seq-ord-2"))
        assert exc.value.details.get("reason") == "fresh_risk_blocked"
        assert "max_position_size" in str(exc.value.details.get("rules", ""))


def test_realized_loss_updates_daily_state_and_blocks_next_order(
    at012_db: tuple[sessionmaker[Session], Settings],
) -> None:
    """Closing at a loss must update DailyRiskState before the next place_paper_order."""

    from app.db.models import Position
    from app.schemas.common import PositionStatus
    from app.schemas.position import ClosePaperPositionRequest
    from app.services.position_service import PositionService

    factory, settings = at012_db
    with factory() as session:
        session.add(
            UserRiskSettings(
                organization_id=ORG_ID,
                user_id=USER_ID,
                daily_loss_limit=Decimal("100"),
                daily_target=None,
                max_trades_per_day=20,
                max_risk_per_trade_percent=Decimal("1"),
                default_account_balance=Decimal("10000"),
                timezone="UTC",
                green_day_protection_enabled=True,
                one_loss_stop_enabled=False,
                overtrading_guard_enabled=True,
            )
        )
        session.commit()

        pid1, aid1 = _seed(session)
        _execution(session, settings).place_paper_order(_request(pid1, aid1, key="loss-ord1"))
        session.commit()

        position = session.scalar(
            select(Position).where(
                Position.organization_id == ORG_ID,
                Position.status == PositionStatus.OPEN,
            )
        )
        assert position is not None
        # size 0.005, entry 60000 → exit 30000 yields -150 realized (< -100 limit)
        PositionService(session, AuditService(session)).close_paper(
            position.id,
            ClosePaperPositionRequest(exit_price=Decimal("30000"), reason="stop"),
        )
        session.commit()

        daily = session.scalar(
            select(DailyRiskState).where(
                DailyRiskState.organization_id == ORG_ID,
                DailyRiskState.user_id == USER_ID,
            )
        )
        assert daily is not None
        assert daily.realized_pnl == Decimal("-150")
        assert daily.locked is True

        pid2, aid2 = _seed(session)
        with pytest.raises(TradingPolicyError) as exc:
            _execution(session, settings).place_paper_order(_request(pid2, aid2, key="loss-ord2"))
        assert exc.value.details.get("reason") == "fresh_risk_blocked"
        assert "max_daily_loss" in str(exc.value.details.get("rules", ""))
