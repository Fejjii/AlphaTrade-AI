"""Verified linear USDT perpetual contracts for the paper Watcher.

A symbol may be configured before it is scan-eligible. It becomes available
only when a provider contract names that exact symbol as a trading linear USDT
perpetual. A payload for a different symbol is rejected and is never used as a
substitute.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

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
    base_asset: str = ""
    price_precision: int | None = None
    quantity_precision: int | None = None
    tick_size: str | None = None
    step_size: str | None = None


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

    def without(self, symbol: str, venue: VenueId) -> ContractBook:
        token = symbol.strip().upper()
        return ContractBook(
            contracts=tuple(
                item
                for item in self.contracts
                if not (item.venue is venue and item.symbol == token)
            )
        )


class ContractCheck(StrEnum):
    """How a provider lookup ended. Unreachable is not an unsupported listing."""

    VERIFIED = "verified"
    UNSUPPORTED = "unsupported"
    UNREACHABLE = "unreachable"


@dataclass(frozen=True, slots=True)
class ContractVerdict:
    symbol: str
    venue: VenueId
    state: ContractCheck
    reason: str
    contract: LinearPerpetualContract | None = None


class ContractProviderUnreachableError(Exception):
    """The provider did not return a contract book. The symbol is not disproven."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def default_contract_book() -> ContractBook:
    """Binance USD-M contracts read from exchangeInfo, plus the Bybit BTC contract.

    The five Binance rows were taken from a `futuresType=U_MARGINED` book on
    2026-09-30. `fapi.binance.com` returned HTTP 451, so the book was read from
    `https://www.binance.com/fapi/v1/exchangeInfo`. That host ignores the symbol
    query and returns the full book; each row below was selected by exact symbol.
    Bybit `instruments-info` returned HTTP 403, so no extra Bybit listing is stored.
    A later provider payload replaces these rows. A failed fetch does not.
    """

    return ContractBook(
        contracts=(
            _binance("BTCUSDT", "BTC", 2, 3, "0.10", "0.001"),
            _binance("ETHUSDT", "ETH", 2, 3, "0.01", "0.001"),
            _binance("ZECUSDT", "ZEC", 2, 3, "0.01", "0.001"),
            _binance("TAOUSDT", "TAO", 2, 3, "0.01", "0.001"),
            _binance("HYPEUSDT", "HYPE", 5, 2, "0.00100", "0.01"),
            LinearPerpetualContract(
                venue=VenueId.BYBIT,
                symbol="BTCUSDT",
                source=BYBIT_LINEAR_SOURCE,
                contract_type="LinearPerpetual",
                quote_asset="USDT",
                status="Trading",
                base_asset="BTC",
            ),
        )
    )


def _binance(
    symbol: str,
    base: str,
    price_precision: int,
    quantity_precision: int,
    tick_size: str,
    step_size: str,
) -> LinearPerpetualContract:
    return LinearPerpetualContract(
        venue=VenueId.BINANCE,
        symbol=symbol,
        source=BINANCE_USDM_SOURCE,
        contract_type="PERPETUAL",
        quote_asset="USDT",
        status="TRADING",
        base_asset=base,
        price_precision=price_precision,
        quantity_precision=quantity_precision,
        tick_size=tick_size,
        step_size=step_size,
    )


def contract_from_binance_exchange_info(
    payload: Mapping[str, object],
    *,
    requested_symbol: str,
) -> LinearPerpetualContract:
    """Read the exchangeInfo row for the requested symbol.

    A full book often starts with BTCUSDT. The first row is never used as a
    stand-in for a different request.
    """

    token, _base = require_linear_usdt_symbol(requested_symbol)
    futures_type = payload.get("futuresType")
    if futures_type is not None and str(futures_type).upper() != "U_MARGINED":
        raise WrongMarketError("exchangeInfo is not a Binance USD-M book.")
    info = _exact_row(payload.get("symbols"), token, label="USD-M exchangeInfo")
    contract_type = str(info.get("contractType", "")).upper()
    if contract_type != "PERPETUAL":
        raise WrongMarketError(f"USD-M contractType {contract_type} is not PERPETUAL.")
    quote = str(info.get("quoteAsset", "")).upper()
    if quote != "USDT":
        raise WrongMarketError("USD-M quote asset is not USDT.")
    status = str(info.get("status", "")).upper()
    if status != "TRADING":
        raise WrongInstrumentError(f"USD-M contract {token} is not TRADING.")
    base = str(info.get("baseAsset", "")).upper()
    if base != _base:
        raise WrongInstrumentError("USD-M base asset does not match the symbol.")
    tick_size, step_size = _binance_precision_filters(info)
    return LinearPerpetualContract(
        venue=VenueId.BINANCE,
        symbol=token,
        source=BINANCE_USDM_SOURCE,
        contract_type=contract_type,
        quote_asset=quote,
        status=status,
        base_asset=base,
        price_precision=_optional_int(info.get("pricePrecision")),
        quantity_precision=_optional_int(info.get("quantityPrecision")),
        tick_size=tick_size,
        step_size=step_size,
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
    info = _exact_row(result.get("list"), token, label="Bybit linear instruments-info")
    contract_type = str(info.get("contractType", ""))
    if contract_type != "LinearPerpetual":
        raise WrongMarketError(f"Bybit contractType {contract_type} is not LinearPerpetual.")
    quote = str(info.get("quoteCoin", "")).upper()
    if quote != "USDT":
        raise WrongMarketError("Bybit linear quote coin is not USDT.")
    status = str(info.get("status", ""))
    if status != "Trading":
        raise WrongInstrumentError(f"Bybit contract {token} is not Trading.")
    base = str(info.get("baseCoin", "")).upper()
    if base and base != _base:
        raise WrongInstrumentError("Bybit base coin does not match the symbol.")
    return LinearPerpetualContract(
        venue=VenueId.BYBIT,
        symbol=token,
        source=BYBIT_LINEAR_SOURCE,
        contract_type=contract_type,
        quote_asset=quote,
        status=status,
        base_asset=base or _base,
        price_precision=_optional_int(info.get("priceScale")),
        quantity_precision=_optional_int(info.get("quantityPrecision")),
        tick_size=_bybit_step(info, "tickSize"),
        step_size=_bybit_step(info, "qtyStep"),
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
    verdicts: Mapping[tuple[str, VenueId], ContractVerdict] | None = None,
) -> tuple[str, str | None]:
    """Return ``(market_source, error_state)``.

    A missing row is unsupported only after a provider book omitted that exact
    symbol. A failed fetch stays ``provider_unreachable`` and does not delete a
    contract that was already proven.
    """

    try:
        token, _base = require_linear_usdt_symbol(symbol)
    except WrongInstrumentError:
        return UNAVAILABLE_SOURCE, "invalid_symbol"
    venue = venue_for_evidence_source(source_mode)
    contract = book.contract_for(token, venue)
    if contract is not None:
        if _replay_mode(source_mode) and token != "BTCUSDT":
            return contract.source, None
        return source_label_for_mode(source_mode), None
    verdict = None if verdicts is None else verdicts.get((token, venue))
    if verdict is not None and verdict.state is ContractCheck.UNSUPPORTED:
        return UNAVAILABLE_SOURCE, "unsupported_contract"
    if verdict is not None and verdict.state is ContractCheck.UNREACHABLE:
        return UNAVAILABLE_SOURCE, "provider_unreachable"
    return UNAVAILABLE_SOURCE, "awaiting_contract_check"


def apply_binance_exchange_info(
    book: ContractBook,
    payload: Mapping[str, object],
    symbols: Sequence[str],
) -> tuple[ContractBook, tuple[ContractVerdict, ...]]:
    """Merge a USD-M book. A missing row removes that symbol. Other rows stay."""

    updated = book
    verdicts: list[ContractVerdict] = []
    for raw in symbols:
        token, _base = require_linear_usdt_symbol(raw)
        try:
            contract = contract_from_binance_exchange_info(payload, requested_symbol=token)
        except (WrongInstrumentError, WrongMarketError):
            updated = updated.without(token, VenueId.BINANCE)
            verdicts.append(
                ContractVerdict(
                    symbol=token,
                    venue=VenueId.BINANCE,
                    state=ContractCheck.UNSUPPORTED,
                    reason="unsupported_contract",
                    contract=None,
                )
            )
            continue
        updated = updated.with_contract(contract)
        verdicts.append(
            ContractVerdict(
                symbol=token,
                venue=VenueId.BINANCE,
                state=ContractCheck.VERIFIED,
                reason="verified",
                contract=contract,
            )
        )
    return updated, tuple(verdicts)


def unreachable_verdicts(
    symbols: Sequence[str],
    *,
    venue: VenueId,
    reason: str,
) -> tuple[ContractVerdict, ...]:
    """A failed fetch. Previously verified rows are not deleted."""

    verdicts: list[ContractVerdict] = []
    for raw in symbols:
        token, _base = require_linear_usdt_symbol(raw)
        verdicts.append(
            ContractVerdict(
                symbol=token,
                venue=venue,
                state=ContractCheck.UNREACHABLE,
                reason=reason,
                contract=None,
            )
        )
    return tuple(verdicts)


def _trading(status: str) -> bool:
    return status in {"TRADING", "Trading"}


def _replay_mode(source_mode: str) -> bool:
    return source_mode.strip().lower().replace("-", "_") in {"replay", "mock", "fixture"}


def _exact_row(rows: object, symbol: str, *, label: str) -> Mapping[str, object]:
    if not isinstance(rows, list) or not rows:
        raise WrongInstrumentError(f"{label} missing {symbol}.")
    match: Mapping[str, object] | None = None
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("symbol", "")).upper() == symbol:
            match = row
            break
    if match is None:
        raise WrongInstrumentError(f"{label} does not list {symbol}.")
    return match


def _binance_precision_filters(info: Mapping[str, object]) -> tuple[str | None, str | None]:
    filters = info.get("filters")
    tick_size: str | None = None
    step_size: str | None = None
    if not isinstance(filters, list):
        return tick_size, step_size
    for item in filters:
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get("filterType", "")).upper()
        if kind == "PRICE_FILTER" and item.get("tickSize") is not None:
            tick_size = str(item.get("tickSize"))
        if kind == "LOT_SIZE" and item.get("stepSize") is not None:
            step_size = str(item.get("stepSize"))
    return tick_size, step_size


def _bybit_step(info: Mapping[str, object], key: str) -> str | None:
    lot = info.get("lotSizeFilter")
    price = info.get("priceFilter")
    if key == "qtyStep" and isinstance(lot, Mapping) and lot.get("qtyStep") is not None:
        return str(lot.get("qtyStep"))
    if key == "tickSize" and isinstance(price, Mapping) and price.get("tickSize") is not None:
        return str(price.get("tickSize"))
    return None


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
