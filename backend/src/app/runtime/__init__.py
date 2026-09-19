"""Production composition for canonical Candidate, eligibility, and TradePlan.

Watcher and Telegram stay disabled unless a later, explicitly authorized task
turns those flags on. This package never enables live trading.
"""

from app.runtime.canonical import (
    CanonicalRuntimeFlags,
    ProductionCanonicalRuntime,
    build_production_canonical_runtime,
    runtime_flags_from_settings,
)

__all__ = [
    "CanonicalRuntimeFlags",
    "ProductionCanonicalRuntime",
    "build_production_canonical_runtime",
    "runtime_flags_from_settings",
]
