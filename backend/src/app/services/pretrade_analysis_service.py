"""Pre-trade analysis engine v1 (Slice 33)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.manual_levels import ManualChartLevelRepository
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.common import PreTradeRecommendation, Timeframe, TradeDirection
from app.schemas.manual_levels import ManualChartLevel
from app.schemas.position_sizing import PositionSizingRequest
from app.schemas.pretrade import PreTradeAnalyzeRequest, PreTradeAnalyzeResponse
from app.schemas.strategy_library import StrategyCard
from app.services.market_data_service import MarketDataService
from app.services.position_sizing_service import PositionSizingService


class PreTradeAnalysisService:
    """Deterministic pre-trade analysis — LLM may explain later, not decide."""

    def __init__(
        self,
        session: Session,
        market_data_service: MarketDataService,
        position_sizing_service: PositionSizingService | None = None,
    ) -> None:
        self._session = session
        self._market = market_data_service
        self._sizing = position_sizing_service or PositionSizingService()
        self._strategies = UserStrategyRepository(session)
        self._levels = ManualChartLevelRepository(session)

    def analyze(self, request: PreTradeAnalyzeRequest) -> PreTradeAnalyzeResponse:
        limitations: list[str] = []
        bullish: list[str] = []
        bearish: list[str] = []

        tf = (
            Timeframe(request.timeframe)
            if request.timeframe in Timeframe._value2member_map_
            else Timeframe.H4
        )
        snapshot = self._market.get_snapshot(request.symbol, tf, exchange=request.exchange)
        indicators = snapshot.indicators
        close = Decimal("0")
        if snapshot.latest_bar is not None:
            close = snapshot.latest_bar.close
        elif snapshot.ticker is not None:
            close = snapshot.ticker.last_price

        if close <= 0:
            limitations.append("No reliable price — using placeholder analysis.")
            close = Decimal("60000")

        direction = request.direction or TradeDirection.LONG
        card: StrategyCard | None = None
        if request.strategy_id is not None:
            strategy = self._strategies.get_scoped(
                request.strategy_id,
                organization_id=request.organization_id,
                user_id=request.user_id,
            )
            if strategy is None:
                limitations.append("Strategy library entry not found.")
            else:
                version = UserStrategyVersionRepository(self._session).latest(strategy.id)
                if version is not None:
                    card = StrategyCard.model_validate(version.card)

        manual_levels: list[ManualChartLevel] = []
        if request.manual_level_ids:
            rows = self._levels.get_many_scoped(
                request.manual_level_ids,
                organization_id=request.organization_id,
                user_id=request.user_id,
            )
            manual_levels = [
                ManualChartLevel.model_validate(row, from_attributes=True) for row in rows
            ]

        ema_fast = indicators.ema_fast if indicators else None
        ema_slow = indicators.ema_slow if indicators else None
        rsi = indicators.rsi if indicators else None
        funding = snapshot.funding_rate

        trend_score = 50.0
        if ema_fast is not None and ema_slow is not None:
            if ema_fast > ema_slow:
                trend_score = 72.0
                bullish.append("EMA fast above EMA slow — bullish structure.")
            elif ema_fast < ema_slow:
                trend_score = 28.0
                bearish.append("EMA fast below EMA slow — bearish structure.")

        volume_score = 55.0
        if snapshot.latest_bar and snapshot.latest_bar.volume > Decimal("0"):
            volume_score = 62.0
            bullish.append("Volume present on latest bar.")

        funding_score = 40.0
        if funding is not None:
            fr = float(funding)
            if fr > 0.0005:
                funding_score = 70.0
                bearish.append("Elevated positive funding — crowded long risk.")
            elif fr < -0.0005:
                funding_score = 65.0
                bearish.append("Negative funding — short squeeze risk for shorts.")

        if rsi is not None:
            if rsi > 70:
                bearish.append(f"RSI overbought ({rsi:.0f}).")
            elif rsi < 30:
                bullish.append(f"RSI oversold ({rsi:.0f}).")

        setup_confidence = trend_score * 0.4 + volume_score * 0.3 + (100 - funding_score) * 0.3
        if card is not None:
            setup_confidence += 5.0
            bullish.append(f"Strategy card loaded: {card.strategy_name}.")
        if manual_levels:
            setup_confidence += min(10.0, len(manual_levels) * 2.0)
            bullish.append(f"{len(manual_levels)} manual level(s) applied.")

        if request.daily_loss_state and request.daily_loss_state.locked:
            bearish.append("Daily loss limit locked — no new risk recommended.")
            setup_confidence = min(setup_confidence, 35.0)

        setup_confidence = max(0.0, min(100.0, setup_confidence))

        stop_pct = Decimal("0.015")
        if direction is TradeDirection.SHORT:
            invalidation_price = close * (Decimal("1") + stop_pct)
        else:
            invalidation_price = close * (Decimal("1") - stop_pct)

        for level in manual_levels:
            if level.price is not None:
                if direction is TradeDirection.LONG and level.price < close:
                    invalidation_price = min(invalidation_price, level.price * Decimal("0.995"))
                elif direction is TradeDirection.SHORT and level.price > close:
                    invalidation_price = max(invalidation_price, level.price * Decimal("1.005"))

        entry_low = close * Decimal("0.998")
        entry_high = close * Decimal("1.002")
        tp_price = close * (
            Decimal("1.03") if direction is TradeDirection.LONG else Decimal("0.97")
        )

        sizing = self._sizing.calculate(
            PositionSizingRequest(
                entry_price=close,
                invalidation_level=invalidation_price,
                account_balance=request.account_size,
                max_risk_percent=request.max_risk_per_trade,
                confidence_score=setup_confidence,
                direction=direction,
                take_profit_price=tp_price,
            )
        )

        regime = (
            "trending" if trend_score >= 60 else "ranging" if trend_score >= 40 else "counter_trend"
        )
        if funding_score >= 65:
            regime = "crowded"

        invalidation_rules = (
            card.invalidation if card else ["Price closes beyond invalidation level."]
        )
        runner_logic = card.runner_plan if card else ["Trail stop after TP1 if runner enabled."]
        tp_levels = [
            {"label": "TP1", "price": str(tp_price.quantize(Decimal("0.01")))},
            {"label": "TP2", "price": str((tp_price * Decimal("1.01")).quantize(Decimal("0.01")))},
        ]

        final_rec = sizing.final_recommendation
        if request.daily_loss_state and request.daily_loss_state.locked:
            final_rec = PreTradeRecommendation.NO_TRADE

        return PreTradeAnalyzeResponse(
            symbol=request.symbol,
            exchange=request.exchange,
            direction_considered=direction,
            bullish_factors=bullish,
            bearish_factors=bearish,
            market_regime=regime,
            trend_alignment_score=trend_score,
            volume_confirmation_score=volume_score,
            funding_risk_score=funding_score,
            setup_confidence_score=setup_confidence,
            risk_reward=sizing.risk_reward_ratio,
            suggested_entry_zone={
                "low": str(entry_low.quantize(Decimal("0.01"))),
                "high": str(entry_high.quantize(Decimal("0.01"))),
            },
            suggested_stop_loss=invalidation_price.quantize(Decimal("0.01")),
            invalidation=invalidation_rules,
            tp_levels=tp_levels,
            runner_logic=runner_logic,
            position_size=sizing,
            leverage_recommendation=sizing.leverage_recommendation,
            final_recommendation=final_rec,
            limitations=limitations or ["Paper-only analysis — no live execution."],
        )
