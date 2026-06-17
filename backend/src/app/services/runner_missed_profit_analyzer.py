"""Conservative runner and missed-profit analysis (Slice 36-37)."""

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
    invalidation_price: Decimal | None = None
    candles_after_exit: list[tuple[datetime, Decimal, Decimal, Decimal, Decimal]] | None = None


class RunnerAndMissedProfitAnalyzer:
    """Detect early exits and estimate conservative missed runner opportunity."""

    LOOKAHEAD_BARS = 24
    MAX_MISSED_CAPTURE_RATIO = Decimal("0.5")

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
        tp2_hit: bool | None = None
        tp3_hit: bool | None = None
        invalidation_hit: bool | None = None

        if data.candles_after_exit:
            window = data.candles_after_exit[: self.LOOKAHEAD_BARS]
            highs = [c[2] for c in window]
            lows = [c[3] for c in window]
            if data.direction == TradeDirection.LONG:
                mfe_after = max(highs) - data.exit_price if highs else None
                mae_after = data.exit_price - min(lows) if lows else None
            else:
                mfe_after = data.exit_price - min(lows) if lows else None
                mae_after = max(highs) - data.exit_price if highs else None

            tp2_hit, tp3_hit = self._tp_levels_hit(data, window)
            invalidation_hit = self._invalidation_hit(data, window)
        else:
            limitations.append(
                "Post-exit candle data unavailable — MFE/MAE after exit not computed."
            )

        early_exit = self._detect_early_exit(data)
        missed_estimate: Decimal | None = None
        would_help: bool | None = None

        if mfe_after is not None and mfe_after > 0:
            missed_estimate = (mfe_after * self.MAX_MISSED_CAPTURE_RATIO).quantize(Decimal("0.01"))
            would_help = data.runner_enabled and mfe_after > abs(
                data.exit_price - data.entry_price
            ) * Decimal("0.25")
            limitations.append(
                "Missed profit capped at 50% of post-exit MFE to reduce hindsight bias."
            )
        elif data.tp_plan_prices:
            remaining = self._remaining_tps(data)
            if remaining:
                missed_estimate = abs(remaining[0] - data.exit_price).quantize(Decimal("0.01"))
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
            tp2_would_have_hit=tp2_hit,
            tp3_would_have_hit=tp3_hit,
            runner_invalidation_would_have_hit=invalidation_hit,
            recommended_lesson=lesson,
            confidence=confidence,
            limitations=limitations,
        )

    def _remaining_tps(self, data: RunnerAnalysisInput) -> list[Decimal]:
        assert data.exit_price is not None
        if data.direction == TradeDirection.LONG:
            return [tp for tp in data.tp_plan_prices if tp > data.exit_price]
        return [tp for tp in data.tp_plan_prices if tp < data.exit_price]

    def _tp_levels_hit(
        self,
        data: RunnerAnalysisInput,
        window: list[tuple[datetime, Decimal, Decimal, Decimal, Decimal]],
    ) -> tuple[bool | None, bool | None]:
        if len(data.tp_plan_prices) < 2:
            return None, None
        sorted_tps = sorted(data.tp_plan_prices, reverse=data.direction == TradeDirection.SHORT)
        tp2 = sorted_tps[1] if len(sorted_tps) > 1 else None
        tp3 = sorted_tps[2] if len(sorted_tps) > 2 else None
        highs = [c[2] for c in window]
        lows = [c[3] for c in window]
        if data.direction == TradeDirection.LONG:
            tp2_hit = tp2 is not None and max(highs) >= tp2
            tp3_hit = tp3 is not None and max(highs) >= tp3
        else:
            tp2_hit = tp2 is not None and min(lows) <= tp2
            tp3_hit = tp3 is not None and min(lows) <= tp3
        return tp2_hit, tp3_hit

    def _invalidation_hit(
        self,
        data: RunnerAnalysisInput,
        window: list[tuple[datetime, Decimal, Decimal, Decimal, Decimal]],
    ) -> bool | None:
        if data.invalidation_price is None:
            return None
        lows = [c[3] for c in window]
        highs = [c[2] for c in window]
        if data.direction == TradeDirection.LONG:
            return min(lows) <= data.invalidation_price
        return max(highs) >= data.invalidation_price

    def _is_winner(self, data: RunnerAnalysisInput) -> bool:
        assert data.entry_price is not None and data.exit_price is not None
        if data.direction == TradeDirection.LONG:
            return data.exit_price > data.entry_price
        return data.exit_price < data.entry_price

    def _detect_early_exit(self, data: RunnerAnalysisInput) -> bool:
        if not data.tp_plan_prices or data.exit_price is None:
            return False
        remaining = self._remaining_tps(data)
        return len(remaining) > 0 and data.runner_enabled

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
