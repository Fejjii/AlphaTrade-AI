"""Family adapter seam shared by Nested simulation and canonical SFP research.

Adapters must emit prefix-stable events in candle order; event timestamps are
closed-candle knowledge times. They never choose fills, risk, or promote versions.
"""

from collections.abc import Iterator
from typing import Any, Protocol

from app.market_contracts.ohlcv import OhlcvBar
from app.schemas.common import BacktestSplitLabel
from app.schemas.nested_continuation import BrainSetupState, NestedContinuationSpec
from app.schemas.strategy_replay import ReplayCandidate
from app.strategy_brain.detector import detect_nested


class ReplayAdapter(Protocol):
    def events(
        self, bars: tuple[OhlcvBar, ...], spec: dict[str, Any], label: BacktestSplitLabel
    ) -> Iterator[tuple[int, ReplayCandidate]]: ...


class NestedReplayAdapter:
    def events(
        self, bars: tuple[OhlcvBar, ...], spec: dict[str, Any], label: BacktestSplitLabel
    ) -> Iterator[tuple[int, ReplayCandidate]]:
        if not bars:
            return
        # The existing detector walks chronologically and confirms pivots only
        # after their right-hand bars close. No retrospective pivot library.
        for event in detect_nested(
            bars, NestedContinuationSpec.model_validate(spec), evaluated_at=bars[-1].interval_end
        ):
            yield (
                event.event_index,
                ReplayCandidate(
                    setup_id=event.setup_id,
                    detected_at=event.detected_at,
                    split_label=label,
                    direction=event.direction,
                    entry=event.entry,
                    stop=event.stop,
                    targets=event.targets,
                    state="confirmed"
                    if event.state is BrainSetupState.CONFIRMED
                    else event.state.value,
                    reasons=event.reason_codes,
                    evidence={key: value.value for key, value in event.evidence.items()},
                    missing_evidence=sorted(
                        key for key, value in event.evidence.items() if value != "AVAILABLE"
                    ),
                ),
            )
