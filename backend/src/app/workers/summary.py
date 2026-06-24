"""Daily summary aggregation for worker system alerts.

Pure aggregation over scan-run rows so it is fully testable without a database
or network. Produces both structured counts and a redaction-safe message.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.db.models import MarketScanRun


@dataclass(frozen=True)
class DailySummary:
    """Aggregated worker activity for a period."""

    total_cycles: int
    successful_cycles: int
    failed_cycles: int
    symbols_scanned: int
    setups_detected: int

    def to_message(self) -> str:
        return (
            "AlphaTrade worker daily summary (paper only)\n"
            f"Cycles: {self.total_cycles} "
            f"(ok {self.successful_cycles}, failed {self.failed_cycles})\n"
            f"Symbols scanned: {self.symbols_scanned}\n"
            f"Setups detected: {self.setups_detected}"
        )


def aggregate_daily_summary(runs: Sequence[MarketScanRun]) -> DailySummary:
    """Aggregate a sequence of scan runs into a :class:`DailySummary`."""
    successful = sum(1 for r in runs if r.status == "success")
    failed = sum(1 for r in runs if r.status == "failed")
    symbols = sum(r.symbols_scanned for r in runs)
    setups = sum(r.setups_detected for r in runs)
    return DailySummary(
        total_cycles=len(runs),
        successful_cycles=successful,
        failed_cycles=failed,
        symbols_scanned=symbols,
        setups_detected=setups,
    )
