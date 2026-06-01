"""Deterministic risk engine: allow and block cases."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.schemas.common import RiskAction, RiskRuleId, TradeDirection
from app.schemas.risk import RiskCheckRequest
from app.services.risk.engine import RiskEngine
from app.services.risk.limits import RiskLimits
from app.services.risk.rules import RiskEvaluationContext
from app.services.risk_service import RiskService


def _request(**kwargs: object) -> RiskCheckRequest:
    base = {
        "symbol": "BTCUSDT",
        "direction": TradeDirection.LONG,
        "entry_price": Decimal("60000"),
        "position_size": Decimal("0.005"),
        "leverage": Decimal("3"),
        "account_equity": Decimal("10000"),
        "stop_loss": Decimal("58000"),
        "volume_24h": Decimal("50000000"),
    }
    base.update(kwargs)
    return RiskCheckRequest(**base)  # type: ignore[arg-type]


def test_risk_engine_allow_case() -> None:
    result = RiskService(RiskEngine(RiskLimits())).check(
        _request(),
        context=RiskEvaluationContext(is_weekend=False, kill_switch_active=False),
    )
    assert result.action is RiskAction.ALLOW
    assert not result.approval_required


def test_risk_engine_block_no_stop_loss() -> None:
    result = RiskService().check(_request(stop_loss=None))
    assert result.action is RiskAction.BLOCK
    assert any(t.rule_id is RiskRuleId.NO_STOP_LOSS for t in result.triggered_rules)


def test_risk_engine_block_kill_switch() -> None:
    result = RiskService().check(
        _request(),
        context=RiskEvaluationContext(kill_switch_active=True, is_weekend=False),
    )
    assert result.action is RiskAction.BLOCK
    assert any(t.rule_id is RiskRuleId.KILL_SWITCH for t in result.triggered_rules)


def test_risk_engine_block_excessive_leverage() -> None:
    result = RiskService(RiskEngine(RiskLimits(max_leverage=Decimal("5")))).check(
        _request(leverage=Decimal("50"))
    )
    assert result.action is RiskAction.BLOCK


@pytest.mark.parametrize("bad_leverage", [Decimal("0"), Decimal("200")])
def test_schema_rejects_invalid_leverage(bad_leverage: Decimal) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _request(leverage=bad_leverage)
