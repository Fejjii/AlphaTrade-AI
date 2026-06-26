"""BloFin positionSide resolution for net vs hedge account modes."""

from __future__ import annotations

from app.providers.exchange.errors import ExchangeRequestError
from app.schemas.common import OrderSide

_NET_MODE = "net_mode"
_HEDGE_MODE = "long_short_mode"


def resolve_position_side(
    position_mode: str,
    side: OrderSide,
    *,
    reduce_only: bool,
) -> str:
    """Map account position mode and order intent to BloFin ``positionSide``.

    Raises :class:`ExchangeRequestError` for unsupported combinations (fail closed).
    """
    mode = position_mode.strip()
    if not mode:
        raise ExchangeRequestError(
            "Refusing order: unknown BloFin position mode (empty).",
            position_mode=None,
        )

    if mode == _NET_MODE:
        return "net"

    if mode == _HEDGE_MODE:
        if reduce_only:
            raise ExchangeRequestError(
                "Refusing order: reduce-only is not supported in BloFin hedge mode.",
                position_mode=mode,
            )
        if side == OrderSide.BUY:
            return "long"
        if side == OrderSide.SELL:
            return "short"
        raise ExchangeRequestError(
            f"Refusing order: unsupported order side {side.value!r}.",
            position_mode=mode,
        )

    raise ExchangeRequestError(
        f"Refusing order: unknown BloFin position mode {mode!r}.",
        position_mode=mode,
    )
