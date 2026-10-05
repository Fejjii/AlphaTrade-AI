"""Symbol gate for later strategy matching.

This does not add setup rules. A compiled strategy is eligible only when its
authored symbol is the symbol being evaluated and the evidence identity names
that same market. Existing BTC strategies therefore still match only BTCUSDT.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.market_contracts.identity import (
    EvidenceMarketIdentity,
    instrument_matches_requested_symbol,
)


@dataclass(frozen=True, slots=True)
class SymbolMarketEvidence:
    """Selected symbol plus the canonical evidence identity, when one exists."""

    symbol: str
    identity: EvidenceMarketIdentity | None
    source: str
    freshness: str


@dataclass(frozen=True, slots=True)
class StrategySymbolMatch:
    """Whether one compiled strategy may consume this symbol's evidence."""

    strategy_symbol: str
    scan_symbol: str
    matched: bool
    reason: str


def strategy_applies_to_symbol(strategy_symbol: str, scan_symbol: str) -> bool:
    """True when both tokens are the same canonical symbol."""

    return strategy_symbol.strip().upper() == scan_symbol.strip().upper()


def match_strategy_to_evidence(
    *,
    strategy_symbol: str,
    evidence: SymbolMarketEvidence,
) -> StrategySymbolMatch:
    """Fail closed when the strategy, the slot, or the evidence market disagree."""

    authored = strategy_symbol.strip().upper()
    scan = evidence.symbol.strip().upper()
    if not strategy_applies_to_symbol(authored, scan):
        return StrategySymbolMatch(
            strategy_symbol=authored,
            scan_symbol=scan,
            matched=False,
            reason="symbol_mismatch",
        )
    if evidence.freshness == "stale":
        return StrategySymbolMatch(
            strategy_symbol=authored,
            scan_symbol=scan,
            matched=False,
            reason="stale_evidence",
        )
    identity = evidence.identity
    if identity is None:
        return StrategySymbolMatch(
            strategy_symbol=authored,
            scan_symbol=scan,
            matched=False,
            reason="missing_evidence",
        )
    if not instrument_matches_requested_symbol(identity, scan):
        return StrategySymbolMatch(
            strategy_symbol=authored,
            scan_symbol=scan,
            matched=False,
            reason="identity_mismatch",
        )
    if identity.provenance.fallback_used:
        return StrategySymbolMatch(
            strategy_symbol=authored,
            scan_symbol=scan,
            matched=False,
            reason="fallback_rejected",
        )
    return StrategySymbolMatch(
        strategy_symbol=authored,
        scan_symbol=scan,
        matched=True,
        reason="symbol_aligned",
    )
