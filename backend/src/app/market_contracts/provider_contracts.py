"""Verified linear USDT perpetual contracts for the paper Watcher.

A symbol may be configured before it is scan-eligible. It becomes available
only when a provider contract names that exact symbol as a trading linear USDT
perpetual. A payload for a different symbol is rejected and is never used as a
substitute.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.market_contracts.enums import VenueId
from app.market_contracts.errors import WrongInstrumentError, WrongMarketError
from app.market_contracts.identity import require_linear_usdt_symbol

BINANCE_USDM_SOURCE = "binance_usdm"
BYBIT_LINEAR_SOURCE = "bybit_usdt_perpetual"
REPLAY_SOURCE = "replay"
UNAVAILABLE_SOURCE = "unavailable"


@dataclass(frozen=True, slots=True)
class LinearPerpetualContract:
    """One verified provider contract. Not a price and not a strategy."""

    venue: VenueId
    symbol: str
    source: str
    contract_type: str
    quote_asset: str
    status: str


@dataclass(frozen=True, slots=True)
class ContractBook:
    """Immutable set of contracts the process may treat as supported."""

    contracts: tuple[LinearPerpetualContract, ...]

    def supports(self, symbol: str, venue: VenueId) -> bool:
        token = symbol.strip().upper()
        return any(
            item.symbol == token and item.venue is venue and _trading(item.status)
            for item in self.contracts
        )

    def contract_for(self, symbol: str, venue: VenueId) -> LinearPerpetualContract | None:
        token = symbol.strip().upper()
        for item in self.contracts:
            if item.symbol == token and item.venue is venue and _trading(item.status):
                return item
        return None

    def with_contract(self, contract: LinearPerpetualContract) -> ContractBook:
        kept = tuple(
            item
            for item in self.contracts
            if not (item.venue is contract.venue and item.symbol == contract.symbol)
        )
        return ContractBook(contracts=(*kept, contract))


def default_contract_book() -> ContractBook:
    """Contracts this repository has already bound to an evidence adapter.

    BTCUSDT is the contracted Binance USD-M and Bybit linear perpetual. Other
    symbols stay unavailable until a provider payload verifies that exact
    contract. This book does not invent listings.
    """

    return ContractBook(
        contracts=(
            LinearPerpetualContract(
                venue=VenueId.BINANCE,
                symbol="BTCUSDT",
                source=BINANCE_USDM_SOURCE,
                contract_type="PERPETUAL",
                quote_asset="USDT",
                status="TRADING",
            ),
            LinearPerpetualContract(
                venue=VenueId.BYBIT,
                symbol="BTCUSDT",
                source=BYBIT_LINEAR_SOURCE,
                contract_type="LinearPerpetual",
                quote_asset="USDT",
                status="Trading",
            ),
        )
    )


def contract_from_binance_exchange_info(
    payload: Mapping[str, object],
    *,
    requested_symbol: str,
) -> LinearPerpetualContract:
    """Read one Binance USD-M exchangeInfo row. A different symbol fails closed."""

    token, _base = require_linear_usdt_symbol(requested_symbol)
    symbols = payload.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        raise WrongInstrumentError(f"USD-M exchangeInfo missing {token}.")
    info = symbols[0]
    if not isinstance(info, Mapping):
        raise WrongMarketError("exchangeInfo symbol row is not an object.")
    reported = str(info.get("symbol", "")).upper()
    if reported != token:
        raise WrongInstrumentError("exchangeInfo symbol does not match the requested instrument.")
    contract_type = str(info.get("contractType", "")).upper()
    if contract_type != "PERPETUAL":
        raise WrongMarketError(f"USD-M contractType {contract_type} is not PERPETUAL.")
    quote = str(info.get("quoteAsset", "")).upper()
    if quote != "USDT":
        raise WrongMarketError("USD-M quote asset is not USDT.")
    status = str(info.get("status", "")).upper()
    if status != "TRADING":
        raise WrongInstrumentError(f"USD-M contract {token} is not TRADING.")
    return LinearPerpetualContract(
        venue=VenueId.BINANCE,
        symbol=token,
        source=BINANCE_USDM_SOURCE,
        contract_type=contract_type,
        quote_asset=quote,
        status=status,
    )


def contract_from_bybit_instruments(
    payload: Mapping[str, object],
    *,
    requested_symbol: str,
) -> LinearPerpetualContract:
    """Read one Bybit linear instrument row. A different symbol fails closed."""

    token, _base = require_linear_usdt_symbol(requested_symbol)
    result = payload.get("result")
    if not isinstance(result, Mapping):
        raise WrongMarketError("Bybit instruments-info result is missing.")
    category = str(result.get("category", "")).lower()
    if category and category != "linear":
        raise WrongMarketError("Bybit instrument category is not linear.")
    rows = result.get("list")
    if not isinstance(rows, list) or not rows:
        raise WrongInstrumentError(f"Bybit linear instruments-info missing {token}.")
    info = rows[0]
    if not isinstance(info, Mapping):
        raise WrongMarketError("Bybit instrument row is not an object.")
    reported = str(info.get("symbol", "")).upper()
    if reported != token:
        raise WrongInstrumentError(
            "Bybit instrument symbol does not match the requested instrument."
        )
    contract_type = str(info.get("contractType", ""))
    if contract_type != "LinearPerpetual":
        raise WrongMarketError(f"Bybit contractType {contract_type} is not LinearPerpetual.")
    quote = str(info.get("quoteCoin", "")).upper()
    if quote != "USDT":
        raise WrongMarketError("Bybit linear quote coin is not USDT.")
    status = str(info.get("status", ""))
    if status != "Trading":
        raise WrongInstrumentError(f"Bybit contract {token} is not Trading.")
    return LinearPerpetualContract(
        venue=VenueId.BYBIT,
        symbol=token,
        source=BYBIT_LINEAR_SOURCE,
        contract_type=contract_type,
        quote_asset=quote,
        status=status,
    )


def venue_for_evidence_source(source_mode: str) -> VenueId:
    """Map the process evidence mode onto the venue whose contract must match.

    Replay uses the Binance USD-M fixture identity. A Bybit contract is not
    used to fill a Binance or replay request.
    """

    mode = source_mode.strip().lower().replace("-", "_")
    if mode in {"bybit_usdt_perpetual", "bybit"}:
        return VenueId.BYBIT
    return VenueId.BINANCE


def source_label_for_mode(source_mode: str) -> str:
    mode = source_mode.strip().lower().replace("-", "_")
    if mode in {"replay", "mock", "fixture"}:
        return REPLAY_SOURCE
    if mode in {"bybit_usdt_perpetual", "bybit"}:
        return BYBIT_LINEAR_SOURCE
    if mode in {"binance_usdm", "usdm"}:
        return BINANCE_USDM_SOURCE
    return mode or UNAVAILABLE_SOURCE


def availability_for_symbol(
    symbol: str,
    *,
    source_mode: str,
    book: ContractBook,
) -> tuple[str, str | None]:
    """Return ``(market_source, error_state)``.

    Unsupported symbols are unavailable. The other venue's contract is not
    substituted.
    """

    try:
        token, _base = require_linear_usdt_symbol(symbol)
    except WrongInstrumentError:
        return UNAVAILABLE_SOURCE, "invalid_symbol"
    venue = venue_for_evidence_source(source_mode)
    if book.contract_for(token, venue) is None:
        return UNAVAILABLE_SOURCE, "contract_unverified"
    return source_label_for_mode(source_mode), None


def _trading(status: str) -> bool:
    return status in {"TRADING", "Trading"}
