"""Read-only BloFin demo account provider.

Exposes instruments, balances, positions, and API-key permissions. The
permission probe is the basis for the platform's hard refusal of any key that
can move funds (withdraw/transfer) - see :func:`resolve_exchange_provider`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog

from app.providers.base import ProviderHealth, ProviderKind, ProviderStatus
from app.providers.exchange.base import (
    AccountPermissions,
    ExchangeBalance,
    ExchangeInstrument,
    ExchangePositionData,
)
from app.providers.exchange.blofin_client import BloFinClient
from app.providers.exchange.mapping import from_blofin_inst_id

logger = structlog.get_logger(__name__)

_WITHDRAW_SCOPES = frozenset({"withdraw", "withdrawal", "transfer", "internal_transfer"})
_TRADE_SCOPES = frozenset({"trade", "trading"})


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


class BloFinAccountProvider:
    """Read-only access to the BloFin demo account."""

    name = "blofin-demo-account"
    kind = ProviderKind.EXCHANGE

    def __init__(self, client: BloFinClient, *, is_demo: bool = True) -> None:
        self._client = client
        self._is_demo = is_demo
        self._permissions_verified_at: datetime | None = None

    def get_instruments(self) -> list[ExchangeInstrument]:
        data = self._client.request(
            "GET", "/api/v1/market/instruments", params={"instType": "SWAP"}
        )
        rows = data if isinstance(data, list) else []
        instruments: list[ExchangeInstrument] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            inst_id = str(row.get("instId", ""))
            if not inst_id:
                continue
            instruments.append(
                ExchangeInstrument(
                    symbol=from_blofin_inst_id(inst_id),
                    inst_id=inst_id,
                    base_currency=str(row.get("baseCurrency", "")),
                    quote_currency=str(row.get("quoteCurrency", "")),
                    instrument_type=str(row.get("instType", "")),
                    tick_size=_to_decimal(row.get("tickSize")) if row.get("tickSize") else None,
                    lot_size=_to_decimal(row.get("lotSize")) if row.get("lotSize") else None,
                    min_size=_to_decimal(row.get("minSize")) if row.get("minSize") else None,
                    contract_size=(
                        _to_decimal(row.get("contractValue")) if row.get("contractValue") else None
                    ),
                    active=str(row.get("state", "live")).lower() in ("live", "active", ""),
                )
            )
        return instruments

    def get_balances(self) -> list[ExchangeBalance]:
        data = self._client.request("GET", "/api/v1/account/balance", signed=True)
        rows = self._coerce_rows(data, key="details")
        balances: list[ExchangeBalance] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            asset = str(row.get("currency", row.get("ccy", "")))
            if not asset:
                continue
            balances.append(
                ExchangeBalance(
                    asset=asset,
                    total=_to_decimal(row.get("balance", row.get("eq", "0"))),
                    available=_to_decimal(row.get("available", row.get("availBal", "0"))),
                )
            )
        return balances

    def get_positions(self) -> list[ExchangePositionData]:
        data = self._client.request("GET", "/api/v1/account/positions", signed=True)
        rows = data if isinstance(data, list) else []
        positions: list[ExchangePositionData] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            inst_id = str(row.get("instId", ""))
            size = _to_decimal(row.get("positions", row.get("pos", "0")))
            if not inst_id or size == 0:
                continue
            positions.append(
                ExchangePositionData(
                    symbol=from_blofin_inst_id(inst_id),
                    inst_id=inst_id,
                    side=str(row.get("positionSide", row.get("posSide", ""))),
                    size=size,
                    entry_price=_to_decimal(row.get("averagePrice", row.get("avgPx", "0"))),
                    mark_price=_to_decimal(row.get("markPrice", row.get("markPx", "0"))),
                    unrealized_pnl=_to_decimal(row.get("unrealizedPnl", row.get("upl", "0"))),
                    leverage=_to_decimal(row.get("leverage", "0")),
                )
            )
        return positions

    def get_account_permissions(self) -> AccountPermissions:
        """Probe the configured API key's scopes.

        Raises an :class:`ExchangeError` subclass if the venue cannot be reached
        or rejects the key; callers decide whether that is fatal.
        """
        data = self._client.request("GET", "/api/v1/user/query-apikey", signed=True)
        row = data[0] if isinstance(data, list) and data else data
        scopes_raw = ""
        if isinstance(row, dict):
            scopes_raw = str(row.get("permissions", row.get("perm", "")))
        scopes = tuple(s.strip().lower() for s in scopes_raw.replace(",", " ").split() if s.strip())
        self._permissions_verified_at = datetime.now(UTC)
        return AccountPermissions(
            can_read=True,
            can_trade=any(s in _TRADE_SCOPES for s in scopes),
            can_withdraw=any(s in _WITHDRAW_SCOPES for s in scopes),
            can_transfer=any(s in {"transfer", "internal_transfer"} for s in scopes),
            raw_scopes=scopes,
        )

    @staticmethod
    def _coerce_rows(data: Any, *, key: str) -> list[Any]:
        if isinstance(data, list):
            # Either a list of detail rows, or a list wrapping a dict with details.
            if data and isinstance(data[0], dict) and key in data[0]:
                return data[0][key]
            return data
        if isinstance(data, dict):
            return data.get(key, [])
        return []

    def status(self) -> ProviderStatus:
        verified = self._permissions_verified_at is not None
        detail = "BloFin demo account (read-only, no withdrawal scope)."
        if not verified:
            detail = "BloFin demo account (read-only); permissions not yet verified."
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            health=ProviderHealth.HEALTHY if verified else ProviderHealth.DEGRADED,
            using_fallback=False,
            is_mock=False,
            detail=detail,
            last_success_at=self._client.last_success_at,
            error_message=self._client.last_error,
        )
