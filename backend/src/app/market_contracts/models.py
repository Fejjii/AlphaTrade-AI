"""Frozen canonical models for market contracts."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def parse_canonical_decimal(value: object) -> Decimal:
    """Parse a finite base-10 decimal; reject floats and booleans."""
    if isinstance(value, bool | float):
        raise ValueError("Binary floating-point and boolean values are not valid decimals.")
    if not isinstance(value, Decimal | int | str):
        raise ValueError("Decimal values must be supplied as a base-10 string or integer.")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid base-10 decimal value.") from exc
    if not parsed.is_finite():
        raise ValueError("Decimal values must be finite.")
    return parsed


CanonicalDecimal = Annotated[Decimal, BeforeValidator(parse_canonical_decimal)]
PositiveCanonicalDecimal = Annotated[
    Decimal,
    BeforeValidator(parse_canonical_decimal),
    Field(gt=0),
]
NonNegativeCanonicalDecimal = Annotated[
    Decimal,
    BeforeValidator(parse_canonical_decimal),
    Field(ge=0),
]


class CanonicalModel(BaseModel):
    """Strict, frozen semantic model with no implicit string normalization."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)
