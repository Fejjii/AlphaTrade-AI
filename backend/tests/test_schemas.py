"""Validation tests for Pydantic schemas (valid + invalid boundaries)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.agent import AgentState, Intent, MessageClass
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.common import (
    RiskAction,
    RiskSeverity,
    StrategyId,
    TradeDirection,
)
from app.schemas.market import WatchlistItemCreate
from app.schemas.proposal import ExitCriteria, TakeProfitLevel, TradeProposal
from app.schemas.risk import RiskCheckRequest, RiskCheckResult
from app.schemas.strategy import EntryZone, StrategySignal


def _now() -> datetime:
    return datetime.now(UTC)


# --- Symbol / timeframe constraints ----------------------------------------- #


def test_symbol_is_uppercased_and_accepts_pair() -> None:
    org = uuid4()
    user = uuid4()
    item = WatchlistItemCreate(
        organization_id=org,
        user_id=user,
        symbol="btc/usdt",
        exchange="binance",
        timeframes=["4h"],
        strategy_ids=[StrategyId.HTF_TREND_PULLBACK],
    )
    assert item.symbol == "BTC/USDT"


@pytest.mark.parametrize("bad_symbol", ["", "B", "BTC USDT", "BTC@USDT", "x" * 31])
def test_invalid_symbol_rejected(bad_symbol: str) -> None:
    with pytest.raises(ValidationError):
        WatchlistItemCreate(
            organization_id=uuid4(),
            user_id=uuid4(),
            symbol=bad_symbol,
            exchange="binance",
            timeframes=["4h"],
            strategy_ids=[StrategyId.HTF_TREND_PULLBACK],
        )


def test_invalid_timeframe_rejected() -> None:
    with pytest.raises(ValidationError):
        WatchlistItemCreate(
            organization_id=uuid4(),
            user_id=uuid4(),
            symbol="BTCUSDT",
            exchange="binance",
            timeframes=["7m"],
            strategy_ids=[StrategyId.HTF_TREND_PULLBACK],
        )


# --- extra=forbid on request models ----------------------------------------- #


def test_request_model_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="a@b.com", password="secret", smuggled="x")


def test_register_password_minimum_length() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@b.com", password="short", organization_name="Acme")


# --- Leverage / confidence / risk percent bounds ---------------------------- #


def _risk_request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "symbol": "BTCUSDT",
        "direction": TradeDirection.LONG,
        "entry_price": Decimal("100"),
        "position_size": Decimal("1"),
        "leverage": Decimal("5"),
        "account_equity": Decimal("10000"),
    }
    base.update(overrides)
    return base


def test_risk_request_valid() -> None:
    req = RiskCheckRequest(**_risk_request())
    assert req.leverage == Decimal("5")


@pytest.mark.parametrize("bad_leverage", [Decimal("0"), Decimal("-1"), Decimal("126")])
def test_leverage_bounds_enforced(bad_leverage: Decimal) -> None:
    with pytest.raises(ValidationError):
        RiskCheckRequest(**_risk_request(leverage=bad_leverage))


@pytest.mark.parametrize("bad_risk_percent", [Decimal("-0.1"), Decimal("100.1")])
def test_risk_percent_bounds_enforced(bad_risk_percent: Decimal) -> None:
    with pytest.raises(ValidationError):
        RiskCheckRequest(**_risk_request(risk_percent=bad_risk_percent))


@pytest.mark.parametrize("bad_confidence", [-0.01, 1.01])
def test_confidence_bounds_enforced(bad_confidence: float) -> None:
    with pytest.raises(ValidationError):
        StrategySignal(
            strategy_id=StrategyId.HTF_TREND_PULLBACK,
            symbol="BTCUSDT",
            timeframe="1h",
            direction=TradeDirection.LONG,
            confidence=bad_confidence,
            invalidation="loses HTF trend",
            timestamp=_now(),
        )


# --- EntryZone / ExitCriteria validators ------------------------------------ #


def test_entry_zone_requires_low_le_high() -> None:
    with pytest.raises(ValidationError):
        EntryZone(low=Decimal("110"), high=Decimal("100"))


def test_exit_criteria_requires_take_profit() -> None:
    with pytest.raises(ValidationError):
        ExitCriteria(invalidation="x", stop_loss=Decimal("90"), take_profits=[])


def test_exit_criteria_rejects_fraction_overflow() -> None:
    with pytest.raises(ValidationError):
        ExitCriteria(
            invalidation="x",
            stop_loss=Decimal("90"),
            take_profits=[
                TakeProfitLevel(price=Decimal("110"), size_fraction=0.7),
                TakeProfitLevel(price=Decimal("120"), size_fraction=0.5),
            ],
        )


def test_trade_proposal_valid() -> None:
    proposal = TradeProposal(
        organization_id=uuid4(),
        user_id=uuid4(),
        strategy_id=StrategyId.HTF_TREND_PULLBACK,
        symbol="ETHUSDT",
        timeframe="4h",
        direction=TradeDirection.LONG,
        entry_price=Decimal("3000"),
        position_size=Decimal("0.5"),
        leverage=Decimal("3"),
        exit=ExitCriteria(
            invalidation="close below 2900",
            stop_loss=Decimal("2900"),
            take_profits=[TakeProfitLevel(price=Decimal("3200"), size_fraction=0.5)],
        ),
        confidence=0.7,
        risk_level=RiskSeverity.MEDIUM,
        rationale="HTF uptrend pullback to EMA support.",
        created_at=_now(),
    )
    assert proposal.exit.stop_loss == Decimal("2900")


# --- Risk result / agent state ---------------------------------------------- #


def test_risk_result_accepts_enum_action() -> None:
    result = RiskCheckResult(
        action=RiskAction.BLOCK,
        severity=RiskSeverity.HIGH,
        explanation="No stop loss provided.",
        approval_required=True,
    )
    assert result.action is RiskAction.BLOCK


def test_agent_state_defaults_and_forbids_extra() -> None:
    state = AgentState(request_id="req-1")
    assert state.intent is Intent.UNKNOWN
    assert state.message_class is MessageClass.UNKNOWN
    assert state.strategy_signals == []
    with pytest.raises(ValidationError):
        AgentState(request_id="req-2", bogus_field=1)
