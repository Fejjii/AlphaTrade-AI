"""Conservative runner and missed-profit analysis (Slice 36)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.schemas.common import AnalysisConfidence, TradeDirection
from app.schemas.human_vs_system import RunnerAnalysis


@dataclass(frozen=True)
class RunnerAnalysisInput:
    entry_price: Decimal | None
    exit_price: Decimal | None
    exit_time: datetime | None
    direction: TradeDirection | None
    tp_plan_prices: list[Decimal]
    runner_enabled: bool
    candles_after_exit: list[tuple[datetime, Decimal, Decimal, Decimal, Decimal]] | None = None


class RunnerAndMissedProfitAnalyzer:
    """Detect early exits and estimate conservative missed runner opportunity."""

    LOOKAHEAD_BARS = 24

    def analyze(self, data: RunnerAnalysisInput) -> RunnerAnalysis:
        limitations: list[str] = []
        if data.entry_price is None or data.exit_price is None:
            limitations.append("Entry or exit price missing — cannot estimate missed profit.")
            return RunnerAnalysis(limitations=limitations)

        if data.direction is None:
            limitations.append("Trade direction missing.")
            return RunnerAnalysis(limitations=limitations)

        is_winner = self._is_winner(data)
        if not is_winner:
            return RunnerAnalysis(
                early_exit_flag=False,
                recommended_lesson=(
                    "This was not a winning exit scenario — runner analysis focuses on "
                    "partial winners closed early."
                ),
                confidence=AnalysisConfidence.MEDIUM,
                limitations=["Runner analysis applies to trades closed in profit."],
            )

        mfe_after: Decimal | None = None
        mae_after: Decimal | None = None
        if data.candles_after_exit:
            highs = [c[2] for c in data.candles_after_exit[: self.LOOKAHEAD_BARS]]
            lows = [c[3] for c in data.candles_after_exit[: self.LOOKAHEAD_BARS]]
            if data.direction == TradeDirection.LONG:
                mfe_after = max(highs) - data.exit_price if highs else None
                mae_after = data.exit_price - min(lows) if lows else None
            else:
                mfe_after = data.exit_price - min(lows) if lows else None
                mae_after = max(highs) - data.exit_price if highs else None
        else:
            limitations.append(
                "Post-exit candle data unavailable — MFE/MAE after exit not computed."
            )

        early_exit = self._detect_early_exit(data)
        missed_estimate: Decimal | None = None
        would_help: bool | None = None

        if mfe_after is not None and mfe_after > 0:
            # Conservative: assume at most 50% of post-exit MFE was realistically capturable.
            missed_estimate = (mfe_after * Decimal("0.5")).quantize(Decimal("0.01"))
            would_help = data.runner_enabled and mfe_after > abs(
                data.exit_price - data.entry_price
            ) * Decimal("0.25")
        elif data.tp_plan_prices:
            remaining = [tp for tp in data.tp_plan_prices if tp > data.exit_price]
            if remaining and data.direction == TradeDirection.LONG:
                missed_estimate = (remaining[0] - data.exit_price).quantize(Decimal("0.01"))
                would_help = data.runner_enabled
                limitations.append("Estimate based on planned TP levels — not guaranteed.")
            elif data.direction == TradeDirection.SHORT:
                remaining_short = [tp for tp in data.tp_plan_prices if tp < data.exit_price]
                if remaining_short:
                    missed_estimate = (data.exit_price - remaining_short[0]).quantize(
                        Decimal("0.01")
                    )
                    would_help = data.runner_enabled
                    limitations.append("Estimate based on planned TP levels — not guaranteed.")

        lesson = self._build_lesson(early_exit, would_help, data.runner_enabled)
        confidence = AnalysisConfidence.HIGH if data.candles_after_exit else AnalysisConfidence.LOW
        if missed_estimate is None:
            limitations.append("Missed profit estimate unavailable — insufficient data.")

        return RunnerAnalysis(
            early_exit_flag=early_exit,
            missed_profit_estimate=missed_estimate,
            max_favorable_excursion_after_exit=mfe_after,
            max_adverse_excursion_after_exit=mae_after,
            would_runner_have_helped=would_help,
            recommended_lesson=lesson,
            confidence=confidence,
            limitations=limitations,
        )

    def _is_winner(self, data: RunnerAnalysisInput) -> bool:
        assert data.entry_price is not None and data.exit_price is not None
        if data.direction == TradeDirection.LONG:
            return data.exit_price > data.entry_price
        return data.exit_price < data.entry_price

    def _detect_early_exit(self, data: RunnerAnalysisInput) -> bool:
        if not data.tp_plan_prices or data.exit_price is None:
            return False
        if data.direction == TradeDirection.LONG:
            unhit = [tp for tp in data.tp_plan_prices if tp > data.exit_price]
            return len(unhit) > 0 and data.runner_enabled
        unhit_short = [tp for tp in data.tp_plan_prices if tp < data.exit_price]
        return len(unhit_short) > 0 and data.runner_enabled

    def _build_lesson(
        self,
        early_exit: bool,
        would_help: bool | None,
        runner_enabled: bool,
    ) -> str:
        if not runner_enabled:
            return (
                "Your plan did not include a runner — consider whether partial exits "
                "with a trailing remainder fit your strategy."
            )
        if early_exit and would_help:
            return (
                "Price continued favorably after your exit. Review whether your runner "
                "rules were clear before entry — this is a learning estimate, not hindsight."
            )
        if early_exit:
            return (
                "You closed before all planned targets. Compare your exit rationale "
                "to your written plan next time."
            )
        return "Exit aligned with or exceeded planned targets based on available data."
