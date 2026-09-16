"""Phase 1 LINEAR quote-exposure formula (CONTRACTS vs BASE)."""

from __future__ import annotations

import inspect
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.errors import ConflictError
from app.schemas.trade_plan import ContractType, QuantityUnit
from app.services import execution_claim, execution_exposure, execution_fills
from app.services.execution_exposure import QuoteExposureError, linear_quote_exposure
from app.services.execution_fills import fill_quote_exposure


def test_contracts_formula_multiplies_then_prices() -> None:
    quote = linear_quote_exposure(
        quantity=Decimal("2"),
        price=Decimal("100.10"),
        quantity_unit=QuantityUnit.CONTRACTS.value,
        contract_multiplier=Decimal("10"),
        contract_type=ContractType.LINEAR.value,
    )
    assert quote == Decimal("2") * Decimal("10") * Decimal("100.10")
    assert quote == Decimal("2002.00")


def test_base_formula_does_not_reapply_multiplier() -> None:
    quote = linear_quote_exposure(
        quantity=Decimal("2"),
        price=Decimal("100.10"),
        quantity_unit=QuantityUnit.BASE.value,
        contract_multiplier=Decimal("10"),
        contract_type=ContractType.LINEAR.value,
    )
    assert quote == Decimal("2") * Decimal("100.10")
    assert quote == Decimal("200.20")
    assert quote != Decimal("2") * Decimal("10") * Decimal("100.10")


def test_inverse_and_quote_units_fail_closed() -> None:
    with pytest.raises(QuoteExposureError) as inverse:
        linear_quote_exposure(
            quantity=Decimal("1"),
            price=Decimal("100"),
            quantity_unit=QuantityUnit.CONTRACTS.value,
            contract_multiplier=Decimal("1"),
            contract_type=ContractType.INVERSE.value,
        )
    assert inverse.value.reason == "inverse_contract_undefined"
    with pytest.raises(QuoteExposureError) as quote_unit:
        linear_quote_exposure(
            quantity=Decimal("1"),
            price=Decimal("100"),
            quantity_unit=QuantityUnit.QUOTE.value,
            contract_multiplier=Decimal("1"),
            contract_type=ContractType.LINEAR.value,
        )
    assert quote_unit.value.reason == "unsupported_quantity_unit"


def test_non_decimal_inputs_fail_closed() -> None:
    with pytest.raises(QuoteExposureError) as exc:
        linear_quote_exposure(
            quantity=2,  # type: ignore[arg-type]
            price=Decimal("100"),
            quantity_unit=QuantityUnit.BASE.value,
            contract_multiplier=Decimal("10"),
            contract_type=ContractType.LINEAR.value,
        )
    assert exc.value.reason == "non_decimal_exposure_input"


def test_fill_quote_exposure_has_no_caller_conversion_parameter() -> None:
    params = inspect.signature(fill_quote_exposure).parameters
    assert "reservation" in params
    assert "fill_quantity" in params
    assert "fill_price" in params
    assert "conversion" not in params
    assert "converted_notional" not in params
    assert "quote_exposure" not in params
    claim_params = inspect.signature(execution_claim.conservative_reservation).parameters
    assert list(claim_params) == ["plan"]


def test_claim_and_fill_use_the_same_linear_formula() -> None:
    assert execution_claim.linear_quote_exposure is linear_quote_exposure
    assert execution_fills.linear_quote_exposure is linear_quote_exposure
    assert execution_exposure.linear_quote_exposure is linear_quote_exposure


def test_fill_contracts_uses_contract_multiplier() -> None:
    reservation = SimpleNamespace(
        contract_type=ContractType.LINEAR.value,
        quantity_unit=QuantityUnit.CONTRACTS.value,
        contract_multiplier=Decimal("10"),
    )
    quote = fill_quote_exposure(
        reservation=reservation,  # type: ignore[arg-type]
        fill_quantity=Decimal("1"),
        fill_price=Decimal("100"),
    )
    assert quote == Decimal("1") * Decimal("10") * Decimal("100")
    assert quote == Decimal("1000")


def test_fill_base_quantity_ignores_contract_multiplier() -> None:
    reservation = SimpleNamespace(
        contract_type=ContractType.LINEAR.value,
        quantity_unit=QuantityUnit.BASE.value,
        contract_multiplier=Decimal("10"),
    )
    quote = fill_quote_exposure(
        reservation=reservation,  # type: ignore[arg-type]
        fill_quantity=Decimal("1"),
        fill_price=Decimal("100"),
    )
    assert quote == Decimal("100")
    assert quote != Decimal("1") * Decimal("10") * Decimal("100")


def test_fill_inverse_fails_closed_using_reservation_semantics() -> None:
    reservation = SimpleNamespace(
        contract_type=ContractType.INVERSE.value,
        quantity_unit=QuantityUnit.CONTRACTS.value,
        contract_multiplier=Decimal("1"),
    )
    with pytest.raises(ConflictError) as exc:
        fill_quote_exposure(
            reservation=reservation,  # type: ignore[arg-type]
            fill_quantity=Decimal("1"),
            fill_price=Decimal("100"),
        )
    assert exc.value.details["reason"] == "inverse_contract_fill_undefined"
