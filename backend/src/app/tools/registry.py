"""Central tool registry for the LangGraph agent (Slice 7)."""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from app.core.config import Settings, get_settings
from app.schemas.common import ToolRiskLevel
from app.schemas.tools import ToolOutput, ToolSpec
from app.services.market_data_service import MarketDataService
from app.services.rag_service import RagService
from app.services.risk_service import RiskService
from app.strategies.registry import get_strategy_registry
from app.tools.base import ToolDefinition


def _stub_execute(name: str) -> ToolOutput:
    return ToolOutput(tool_name=name, success=True, result={"status": "mock", "mode": "paper"})


def _risk_checker_execute(args: dict[str, Any]) -> ToolOutput:
    from app.schemas.risk import RiskCheckRequest

    start = time.perf_counter()
    try:
        request = RiskCheckRequest.model_validate(args.get("request", args))
        result = RiskService().check(request)
        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="risk_checker",
            success=True,
            result=result.model_dump(mode="json"),
            latency_ms=latency,
        )
    except Exception as exc:
        return ToolOutput(tool_name="risk_checker", success=False, error=str(exc))


def _optional_decimal(args: dict[str, Any], key: str) -> Decimal | None:
    from decimal import Decimal

    raw = args.get(key)
    return Decimal(str(raw)) if raw is not None else None


def _strategy_evaluator_execute(args: dict[str, Any]) -> ToolOutput:
    from decimal import Decimal

    from app.schemas.common import StrategyId, Timeframe, TradeDirection
    from app.strategies.base import StrategyEvaluationInput

    start = time.perf_counter()
    try:
        strategy_id = StrategyId(args["strategy_id"])
        module = get_strategy_registry().get(strategy_id)
        if module is None:
            return ToolOutput(
                tool_name="strategy_evaluator",
                success=False,
                error="Unknown strategy",
            )
        htf = args.get("htf_trend")
        stress = args.get("stress_score")
        data = StrategyEvaluationInput(
            symbol=str(args.get("symbol", "BTCUSDT")),
            timeframe=Timeframe(str(args.get("timeframe", "4h"))),
            close=Decimal(str(args.get("close", "60000"))),
            volume=Decimal(str(args.get("volume", "1000000"))),
            funding_rate=_optional_decimal(args, "funding_rate"),
            ema_fast=_optional_decimal(args, "ema_fast"),
            ema_slow=_optional_decimal(args, "ema_slow"),
            htf_trend=TradeDirection(htf) if htf else None,
            liquidity_sweep_detected=bool(args.get("liquidity_sweep_detected", False)),
            momentum_exhausted=bool(args.get("momentum_exhausted", False)),
            at_confluence_level=bool(args.get("at_confluence_level", False)),
            green_day_active=bool(args.get("green_day_active", False)),
            stress_score=int(stress) if stress is not None else None,
            tags=dict(args.get("tags", {})),
        )
        signal = module.evaluate(data)
        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="strategy_evaluator",
            success=True,
            result={"signal": signal.model_dump(mode="json") if signal else None},
            latency_ms=latency,
        )
    except Exception as exc:
        return ToolOutput(tool_name="strategy_evaluator", success=False, error=str(exc))


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name=t.name,
                description=t.description,
                risk_level=t.risk_level,
                requires_approval=t.requires_approval,
                provider_dependencies=list(t.provider_dependencies),
                has_fallback=t.has_fallback,
                enabled=t.enabled,
            )
            for t in self._tools.values()
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolOutput:
        tool = self._tools.get(name)
        if tool is None:
            return ToolOutput(tool_name=name, success=False, error=f"Unknown tool: {name}")
        if not tool.enabled:
            return ToolOutput(tool_name=name, success=False, error="Tool is disabled.")
        return tool.execute(arguments)


def _rag_retriever_execute(args: dict[str, Any], rag_service: RagService) -> ToolOutput:
    from app.schemas.rag import RagQuery

    start = time.perf_counter()
    try:
        payload = dict(args)
        query_text = str(payload.pop("query", ""))
        query = RagQuery.model_validate({"query": query_text, **payload})
        result = rag_service.search(query)
        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="rag_retriever",
            success=True,
            result={
                "chunks": [chunk.model_dump(mode="json") for chunk in result.chunks],
                "citations": [cite.model_dump(mode="json") for cite in result.citations],
                "context_only": True,
                "not_trading_signal": True,
            },
            latency_ms=latency,
        )
    except Exception as exc:
        return ToolOutput(tool_name="rag_retriever", success=False, error=str(exc))


def _market_data_execute(
    args: dict[str, Any], market_data_service: MarketDataService
) -> ToolOutput:
    from app.schemas.common import Timeframe

    start = time.perf_counter()
    try:
        symbol = str(args.get("symbol", "BTCUSDT"))
        tf = Timeframe(str(args.get("timeframe", "4h")))
        exchange = str(args.get("exchange", "binance"))
        snapshot = market_data_service.get_snapshot(symbol, tf, exchange=exchange)
        latest = snapshot.latest_bar
        latency = (time.perf_counter() - start) * 1000
        close_val = "0"
        if latest is not None:
            close_val = str(latest.close)
        elif snapshot.ticker is not None:
            close_val = str(snapshot.ticker.last_price)
        return ToolOutput(
            tool_name="market_data",
            success=True,
            result={
                "symbol": symbol,
                "timeframe": tf.value,
                "close": close_val,
                "source": snapshot.meta.source,
                "is_live": snapshot.meta.is_live,
                "is_stale": snapshot.meta.is_stale,
                "fallback_used": snapshot.meta.fallback_used,
                "provider_name": snapshot.meta.provider_name,
                "retrieved_at": snapshot.meta.retrieved_at.isoformat(),
            },
            latency_ms=latency,
            used_fallback=snapshot.meta.fallback_used,
        )
    except Exception as exc:
        return ToolOutput(tool_name="market_data", success=False, error=str(exc))


def _indicator_execute(args: dict[str, Any], market_data_service: MarketDataService) -> ToolOutput:
    from app.schemas.common import Timeframe

    start = time.perf_counter()
    try:
        symbol = str(args.get("symbol", "BTCUSDT"))
        tf = Timeframe(str(args.get("timeframe", "4h")))
        exchange = str(args.get("exchange", "binance"))
        ohlcv = market_data_service.get_ohlcv(symbol, tf, exchange=exchange)
        snap = market_data_service.get_snapshot(symbol, tf, exchange=exchange)
        from app.providers.market_data import OHLCVBar
        from app.services.indicator_service import IndicatorService

        bars = [
            OHLCVBar(
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
                timestamp=b.timestamp,
            )
            for b in ohlcv.bars
        ]
        indicators = IndicatorService().calculate(
            symbol=symbol,
            timeframe=tf,
            bars=bars,
            funding_rate=snap.funding_rate,
        )
        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="indicator",
            success=True,
            result={
                **indicators.model_dump(mode="json"),
                "source": ohlcv.meta.source,
                "is_live": ohlcv.meta.is_live,
                "fallback_used": ohlcv.meta.fallback_used,
            },
            latency_ms=latency,
            used_fallback=ohlcv.meta.fallback_used,
        )
    except Exception as exc:
        return ToolOutput(tool_name="indicator", success=False, error=str(exc))


def _analytics_summary_execute(args: dict[str, Any], session: Any | None) -> ToolOutput:
    import uuid as _uuid

    from app.schemas.analytics import AnalyticsSummaryRequest
    from app.services.analytics.facade import TradingAnalyticsFacade

    start = time.perf_counter()
    if session is None:
        return ToolOutput(
            tool_name="analytics_summary_tool",
            success=False,
            error="Database session required for analytics.",
        )
    try:
        org_raw = args.get("organization_id")
        user_raw = args.get("user_id")
        if org_raw is None or user_raw is None:
            return ToolOutput(
                tool_name="analytics_summary_tool",
                success=False,
                error="organization_id and user_id are required.",
            )
        request = AnalyticsSummaryRequest(
            organization_id=_uuid.UUID(str(org_raw)),
            user_id=_uuid.UUID(str(user_raw)),
            start_date=args.get("start_date"),
            end_date=args.get("end_date"),
            setup_type=args.get("setup_type"),
        )
        summary = TradingAnalyticsFacade(session).summary_tool(request)
        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="analytics_summary_tool",
            success=True,
            result=summary.model_dump(mode="json"),
            latency_ms=latency,
        )
    except Exception as exc:
        return ToolOutput(tool_name="analytics_summary_tool", success=False, error=str(exc))


def _strategy_library_execute(args: dict[str, Any], session: Any | None) -> ToolOutput:
    import uuid as _uuid

    from app.schemas.strategy_library import UserStrategyCreate
    from app.services.strategy_library_service import StrategyLibraryService

    start = time.perf_counter()
    if session is None:
        return ToolOutput(
            tool_name="strategy_library_tool", success=False, error="DB session required."
        )
    try:
        action = str(args.get("action", "list"))
        org = _uuid.UUID(str(args["organization_id"]))
        user = _uuid.UUID(str(args["user_id"]))
        service = StrategyLibraryService(session)
        if action == "list":
            items, total = service.list_strategies(organization_id=org, user_id=user, limit=20)
            result = {"items": [i.model_dump(mode="json") for i in items], "total": total}
        elif action == "get":
            sid = _uuid.UUID(str(args["strategy_id"]))
            result = service.get(sid, organization_id=org, user_id=user).model_dump(mode="json")
        elif action == "create":
            create_args = {k: v for k, v in args.items() if k != "action"}
            payload = UserStrategyCreate.model_validate(
                {**create_args, "organization_id": org, "user_id": user}
            )
            result = service.create(payload).model_dump(mode="json")
        else:
            return ToolOutput(
                tool_name="strategy_library_tool", success=False, error="Unknown action."
            )
        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="strategy_library_tool", success=True, result=result, latency_ms=latency
        )
    except Exception as exc:
        return ToolOutput(tool_name="strategy_library_tool", success=False, error=str(exc))


def _backtest_tool_execute(args: dict[str, Any], session: Any | None, settings: Any) -> ToolOutput:
    import uuid as _uuid

    from app.schemas.backtest import BacktestAssumptions, BacktestRunCreate
    from app.services.backtest_service import BacktestService

    start = time.perf_counter()
    if session is None:
        return ToolOutput(tool_name="backtest_tool", success=False, error="DB session required.")
    try:
        action = str(args.get("action", "latest_result"))
        org = _uuid.UUID(str(args["organization_id"]))
        user = _uuid.UUID(str(args["user_id"]))
        service = BacktestService(session, settings)

        if action == "run":
            sid = _uuid.UUID(str(args["strategy_id"]))
            assumptions = BacktestAssumptions.model_validate(args.get("assumptions") or {})
            run = service.create(
                sid,
                BacktestRunCreate(assumptions=assumptions),
                organization_id=org,
                user_id=user,
            )
            result = run.model_dump(mode="json")
        elif action == "latest_result":
            sid = _uuid.UUID(str(args["strategy_id"]))
            items, _ = service.list_for_strategy(sid, organization_id=org, user_id=user, limit=1)
            if not items:
                result = {"message": "No backtest runs found for this strategy."}
            else:
                result = items[0].model_dump(mode="json")
        elif action == "eligibility":
            from app.services.strategy_library_service import StrategyLibraryService

            sid = _uuid.UUID(str(args["strategy_id"]))
            strategy = StrategyLibraryService(session).get(sid, organization_id=org, user_id=user)
            result = {
                "strategy_id": str(sid),
                "paper_eligible": strategy.paper_eligible,
                "validation_status": strategy.validation_status,
                "backtest_status": strategy.backtest_status,
            }
        else:
            return ToolOutput(tool_name="backtest_tool", success=False, error="Unknown action.")
        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="backtest_tool", success=True, result=result, latency_ms=latency
        )
    except Exception as exc:
        return ToolOutput(tool_name="backtest_tool", success=False, error=str(exc))


def _pretrade_analysis_execute(
    args: dict[str, Any], session: Any | None, mds: MarketDataService
) -> ToolOutput:
    import uuid as _uuid

    from app.schemas.pretrade import PreTradeAnalyzeRequest
    from app.services.pretrade_analysis_service import PreTradeAnalysisService

    start = time.perf_counter()
    if session is None:
        return ToolOutput(
            tool_name="pretrade_analysis_tool", success=False, error="DB session required."
        )
    try:
        payload = dict(args)
        payload["organization_id"] = _uuid.UUID(str(payload["organization_id"]))
        payload["user_id"] = _uuid.UUID(str(payload["user_id"]))
        request = PreTradeAnalyzeRequest.model_validate(payload)
        result = PreTradeAnalysisService(session, mds).analyze(request)
        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="pretrade_analysis_tool",
            success=True,
            result=result.model_dump(mode="json"),
            latency_ms=latency,
        )
    except Exception as exc:
        return ToolOutput(tool_name="pretrade_analysis_tool", success=False, error=str(exc))


def _position_sizing_execute(args: dict[str, Any]) -> ToolOutput:
    from app.schemas.position_sizing import PositionSizingRequest
    from app.services.position_sizing_service import PositionSizingService

    start = time.perf_counter()
    try:
        request = PositionSizingRequest.model_validate(args.get("request", args))
        result = PositionSizingService().calculate(request)
        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="position_sizing_tool",
            success=True,
            result=result.model_dump(mode="json"),
            latency_ms=latency,
        )
    except Exception as exc:
        return ToolOutput(tool_name="position_sizing_tool", success=False, error=str(exc))


def _manual_levels_execute(args: dict[str, Any], session: Any | None) -> ToolOutput:
    import uuid as _uuid

    from app.services.manual_level_service import ManualLevelService

    start = time.perf_counter()
    if session is None:
        return ToolOutput(
            tool_name="manual_levels_tool", success=False, error="DB session required."
        )
    try:
        action = str(args.get("action", "list"))
        org = _uuid.UUID(str(args["organization_id"]))
        user = _uuid.UUID(str(args["user_id"]))
        service = ManualLevelService(session)
        if action == "list":
            items, total = service.list_levels(
                organization_id=org,
                user_id=user,
                symbol=args.get("symbol"),
                exchange=args.get("exchange"),
            )
            result = {"items": [i.model_dump(mode="json") for i in items], "total": total}
        else:
            lid = _uuid.UUID(str(args["level_id"]))
            result = service.get(lid, organization_id=org, user_id=user).model_dump(mode="json")
        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="manual_levels_tool", success=True, result=result, latency_ms=latency
        )
    except Exception as exc:
        return ToolOutput(tool_name="manual_levels_tool", success=False, error=str(exc))


def _human_vs_system_execute(args: dict[str, Any], session: Any | None) -> ToolOutput:
    import uuid as _uuid

    from app.services.human_vs_system_service import HumanVsSystemService

    start = time.perf_counter()
    if session is None:
        return ToolOutput(
            tool_name="human_vs_system_tool", success=False, error="DB session required."
        )
    try:
        trade_id = _uuid.UUID(str(args["trade_id"]))
        org = _uuid.UUID(str(args["organization_id"]))
        user = _uuid.UUID(str(args["user_id"]))
        result = HumanVsSystemService(session).compare(trade_id, organization_id=org, user_id=user)
        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="human_vs_system_tool",
            success=True,
            result=result.model_dump(mode="json"),
            latency_ms=latency,
        )
    except Exception as exc:
        return ToolOutput(tool_name="human_vs_system_tool", success=False, error=str(exc))


def _strategy_testability_execute(args: dict[str, Any], session: Any | None) -> ToolOutput:
    import uuid as _uuid

    from app.services.strategy_testability_service import StrategyTestabilityService

    start = time.perf_counter()
    if session is None:
        return ToolOutput(
            tool_name="strategy_testability_tool", success=False, error="DB session required."
        )
    try:
        org = _uuid.UUID(str(args["organization_id"]))
        user = _uuid.UUID(str(args["user_id"]))
        service = StrategyTestabilityService(session)
        if args.get("strategy_id"):
            result = service.score(
                _uuid.UUID(str(args["strategy_id"])),
                organization_id=org,
                user_id=user,
            )
        else:
            from app.repositories.strategy_library import UserStrategyRepository

            rows, _ = UserStrategyRepository(session).list_scoped(
                organization_id=org, user_id=user, limit=1, offset=0
            )
            if not rows:
                return ToolOutput(
                    tool_name="strategy_testability_tool",
                    success=False,
                    error="No strategies found.",
                )
            result = service.score(rows[0].id, organization_id=org, user_id=user)
        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="strategy_testability_tool",
            success=True,
            result=result.model_dump(mode="json"),
            latency_ms=latency,
        )
    except Exception as exc:
        return ToolOutput(tool_name="strategy_testability_tool", success=False, error=str(exc))


def _lesson_review_execute(args: dict[str, Any], session: Any | None) -> ToolOutput:
    import uuid as _uuid

    from app.schemas.common import LessonCandidateStatus
    from app.schemas.lesson import LessonCandidateAccept, LessonCandidateReject
    from app.services.lesson_candidate_service import LessonCandidateService

    start = time.perf_counter()
    if session is None:
        return ToolOutput(
            tool_name="lesson_review_tool", success=False, error="DB session required."
        )
    try:
        org = _uuid.UUID(str(args["organization_id"]))
        user = _uuid.UUID(str(args["user_id"]))
        action = str(args.get("action", "list_pending"))
        service = LessonCandidateService(session)
        summary = ""
        pending_observation = False
        result_payload: dict[str, Any] = {}

        if action == "list_pending":
            items, total = service.list_candidates(
                organization_id=org,
                user_id=user,
                status=LessonCandidateStatus.PENDING_REVIEW,
                limit=10,
            )
            summary = f"{total} lesson(s) pending review."
            result_payload = {
                "items": [i.model_dump(mode="json") for i in items],
                "pending_observation": True,
            }
            pending_observation = True
        elif action == "list_accepted":
            items, total = service.list_accepted(organization_id=org, user_id=user, limit=10)
            summary = f"{total} accepted lesson(s)."
            result_payload = {"items": [i.model_dump(mode="json") for i in items]}
        elif action == "list_early_exit":
            items, total = service.list_accepted(
                organization_id=org, user_id=user, mistake_type="early_exit", limit=10
            )
            summary = f"{total} accepted lesson(s) related to early exits."
            result_payload = {"items": [i.model_dump(mode="json") for i in items]}
        elif action == "list_stop_refusal":
            items, total = service.list_accepted(
                organization_id=org, user_id=user, mistake_type="stop_violation", limit=10
            )
            summary = f"{total} accepted lesson(s) related to stop discipline."
            result_payload = {"items": [i.model_dump(mode="json") for i in items]}
        elif action == "accept":
            lesson_id = args.get("lesson_id")
            if not lesson_id:
                return ToolOutput(
                    tool_name="lesson_review_tool",
                    success=False,
                    error="Provide lesson_id to accept.",
                )
            accepted = service.accept(
                _uuid.UUID(str(lesson_id)),
                LessonCandidateAccept(reviewer_notes="Accepted via agent."),
                organization_id=org,
                user_id=user,
            )
            session.commit()
            summary = f"Lesson accepted: {accepted.lesson_text[:120]}"
            result_payload = accepted.model_dump(mode="json")
        elif action == "reject":
            lesson_id = args.get("lesson_id")
            if not lesson_id:
                return ToolOutput(
                    tool_name="lesson_review_tool",
                    success=False,
                    error="Provide lesson_id to reject.",
                )
            rejected = service.reject(
                _uuid.UUID(str(lesson_id)),
                LessonCandidateReject(reviewer_notes="Rejected via agent."),
                organization_id=org,
                user_id=user,
            )
            session.commit()
            summary = "Lesson rejected — kept for audit trail."
            result_payload = rejected.model_dump(mode="json")
            pending_observation = True
        elif action == "rule_suggest":
            lesson_id = args.get("lesson_id")
            if lesson_id:
                lesson = service.get(_uuid.UUID(str(lesson_id)), organization_id=org, user_id=user)
                proposed = lesson.proposed_rule_update
                if proposed:
                    summary = f"Proposed rule update: {proposed.summary}"
                else:
                    summary = (
                        "No proposed rule on this lesson — review lesson text and Strategy Lab."
                    )
                result_payload = lesson.model_dump(mode="json")
                pending_observation = lesson.status != LessonCandidateStatus.ACCEPTED
            else:
                summary = "Provide a lesson_id to see proposed rule updates."
        elif action == "runner_rule_hint":
            summary = (
                "Add a runner_structure_break exit block in Strategy Lab after partial TP. "
                "Real trading remains disabled — paper only."
            )
        else:
            return ToolOutput(
                tool_name="lesson_review_tool", success=False, error=f"Unknown action: {action}"
            )

        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="lesson_review_tool",
            success=True,
            result={
                "summary": summary,
                "pending_observation": pending_observation,
                **result_payload,
            },
            latency_ms=latency,
        )
    except Exception as exc:
        return ToolOutput(tool_name="lesson_review_tool", success=False, error=str(exc))


def _structure_from_text_execute(args: dict[str, Any]) -> ToolOutput:
    from app.schemas.structured_rules import StructureFromTextRequest
    from app.services.structure_from_text_service import StructureFromTextService

    start = time.perf_counter()
    try:
        result = StructureFromTextService().draft(
            StructureFromTextRequest(text=str(args.get("text", "")))
        )
        latency = (time.perf_counter() - start) * 1000
        return ToolOutput(
            tool_name="structure_from_text_tool",
            success=True,
            result=result.model_dump(mode="json"),
            latency_ms=latency,
        )
    except Exception as exc:
        return ToolOutput(tool_name="structure_from_text_tool", success=False, error=str(exc))


def build_default_registry(
    _settings: Settings | None = None,
    rag_service: RagService | None = None,
    market_data_service: MarketDataService | None = None,
    db_session: Any | None = None,
) -> ToolRegistry:
    from app.services.rag_service import build_rag_service

    settings = _settings or get_settings()
    rag = rag_service or build_rag_service(settings)
    if market_data_service is None:
        from app.providers.factory import resolve_market_data_provider
        from app.services.indicator_service import IndicatorService
        from app.services.market_cache import MarketDataCache
        from app.services.market_data_service import MarketDataService
        from app.services.strategy_service import StrategyService
        from app.strategies.registry import get_strategy_registry

        market_data_service = MarketDataService(
            resolve_market_data_provider(settings),
            cache=MarketDataCache(settings),
            indicator_service=IndicatorService(),
            strategy_service=StrategyService(registry=get_strategy_registry()),
        )
    mds = market_data_service
    registry = ToolRegistry()
    tools = [
        ToolDefinition(
            name="rag_retriever",
            description="Retrieve playbook and journal context from the knowledge base.",
            risk_level=ToolRiskLevel.READ,
            requires_approval=False,
            provider_dependencies=("mock-embeddings", "qdrant"),
            has_fallback=True,
            enabled=True,
            execute=lambda args: _rag_retriever_execute(args, rag),
        ),
        ToolDefinition(
            name="market_data",
            description="Fetch candles, price, and volume for a symbol.",
            risk_level=ToolRiskLevel.READ,
            requires_approval=False,
            provider_dependencies=("binance-public", "mock-market-data"),
            has_fallback=True,
            enabled=True,
            execute=lambda args: _market_data_execute(args, mds),
        ),
        ToolDefinition(
            name="indicator",
            description="Compute RSI, EMA, MACD, and related indicators.",
            risk_level=ToolRiskLevel.READ,
            requires_approval=False,
            provider_dependencies=("binance-public", "mock-market-data"),
            has_fallback=True,
            enabled=True,
            execute=lambda args: _indicator_execute(args, mds),
        ),
        ToolDefinition(
            name="funding",
            description="Fetch funding rate and crowd imbalance context.",
            risk_level=ToolRiskLevel.READ,
            requires_approval=False,
            provider_dependencies=("mock-market-data",),
            has_fallback=True,
            enabled=True,
            execute=lambda _a: _stub_execute("funding"),
        ),
        ToolDefinition(
            name="risk_checker",
            description="Run the deterministic risk engine on a candidate trade.",
            risk_level=ToolRiskLevel.MEDIUM,
            requires_approval=False,
            provider_dependencies=(),
            has_fallback=False,
            enabled=True,
            execute=_risk_checker_execute,
        ),
        ToolDefinition(
            name="strategy_evaluator",
            description="Evaluate a deterministic strategy module for a setup signal.",
            risk_level=ToolRiskLevel.LOW,
            requires_approval=False,
            provider_dependencies=(),
            has_fallback=False,
            enabled=True,
            execute=_strategy_evaluator_execute,
        ),
        ToolDefinition(
            name="scenario_simulator",
            description="Simulate outcomes for a proposed plan (no execution).",
            risk_level=ToolRiskLevel.LOW,
            requires_approval=False,
            provider_dependencies=(),
            has_fallback=False,
            enabled=True,
            execute=lambda _a: _stub_execute("scenario_simulator"),
        ),
        ToolDefinition(
            name="journal_writer",
            description="Persist a trade journal entry.",
            risk_level=ToolRiskLevel.MEDIUM,
            requires_approval=True,
            provider_dependencies=(),
            has_fallback=False,
            enabled=True,
            execute=lambda _a: _stub_execute("journal_writer"),
        ),
        ToolDefinition(
            name="position_reader",
            description="Read open positions and exposure for the user.",
            risk_level=ToolRiskLevel.READ,
            requires_approval=False,
            provider_dependencies=(),
            has_fallback=False,
            enabled=True,
            execute=lambda _a: _stub_execute("position_reader"),
        ),
        ToolDefinition(
            name="paper_execution",
            description="Place a paper trade order (no real exchange).",
            risk_level=ToolRiskLevel.SENSITIVE,
            requires_approval=True,
            provider_dependencies=("mock-exchange",),
            has_fallback=False,
            enabled=True,
            execute=lambda _a: _stub_execute("paper_execution"),
        ),
        ToolDefinition(
            name="analytics_summary_tool",
            description=(
                "Summarize setup statistics, discipline score, repeated mistakes, "
                "and improvement suggestions for the tenant."
            ),
            risk_level=ToolRiskLevel.READ,
            requires_approval=False,
            provider_dependencies=(),
            has_fallback=False,
            enabled=True,
            execute=lambda args: _analytics_summary_execute(args, db_session),
        ),
        ToolDefinition(
            name="strategy_library_tool",
            description="List, get, or create user strategy cards in the strategy library.",
            risk_level=ToolRiskLevel.LOW,
            requires_approval=False,
            provider_dependencies=(),
            has_fallback=False,
            enabled=True,
            execute=lambda args: _strategy_library_execute(args, db_session),
        ),
        ToolDefinition(
            name="pretrade_analysis_tool",
            description="Run deterministic pre-trade analysis for a symbol and setup.",
            risk_level=ToolRiskLevel.LOW,
            requires_approval=False,
            provider_dependencies=("mock-market-data",),
            has_fallback=True,
            enabled=True,
            execute=lambda args: _pretrade_analysis_execute(args, db_session, mds),
        ),
        ToolDefinition(
            name="position_sizing_tool",
            description="Calculate position size, risk/reward, and confidence-adjusted sizing.",
            risk_level=ToolRiskLevel.LOW,
            requires_approval=False,
            provider_dependencies=(),
            has_fallback=False,
            enabled=True,
            execute=_position_sizing_execute,
        ),
        ToolDefinition(
            name="manual_levels_tool",
            description="List or get manual chart levels for a symbol.",
            risk_level=ToolRiskLevel.READ,
            requires_approval=False,
            provider_dependencies=(),
            has_fallback=False,
            enabled=True,
            execute=lambda args: _manual_levels_execute(args, db_session),
        ),
        ToolDefinition(
            name="human_vs_system_tool",
            description=("Compare actual trade behavior to the system plan and adherence score."),
            risk_level=ToolRiskLevel.READ,
            requires_approval=False,
            provider_dependencies=(),
            has_fallback=False,
            enabled=True,
            execute=lambda args: _human_vs_system_execute(args, db_session),
        ),
        ToolDefinition(
            name="strategy_testability_tool",
            description="Score strategy testability and list missing rule fields.",
            risk_level=ToolRiskLevel.READ,
            requires_approval=False,
            provider_dependencies=(),
            has_fallback=False,
            enabled=True,
            execute=lambda args: _strategy_testability_execute(args, db_session),
        ),
        ToolDefinition(
            name="structure_from_text_tool",
            description="Draft structured rule blocks from plain English (requires validation).",
            risk_level=ToolRiskLevel.LOW,
            requires_approval=False,
            provider_dependencies=(),
            has_fallback=False,
            enabled=True,
            execute=_structure_from_text_execute,
        ),
        ToolDefinition(
            name="lesson_review_tool",
            description=(
                "List, accept, or reject lesson candidates; "
                "query accepted lessons and rule updates."
            ),
            risk_level=ToolRiskLevel.MEDIUM,
            requires_approval=False,
            provider_dependencies=(),
            has_fallback=False,
            enabled=True,
            execute=lambda args: _lesson_review_execute(args, db_session),
        ),
        ToolDefinition(
            name="backtest_tool",
            description=(
                "Run deterministic backtest v1, fetch latest results, or check paper eligibility."
            ),
            risk_level=ToolRiskLevel.LOW,
            requires_approval=False,
            provider_dependencies=("mock-market-data",),
            has_fallback=True,
            enabled=True,
            execute=lambda args: _backtest_tool_execute(args, db_session, settings),
        ),
    ]
    for tool in tools:
        registry.register(tool)
    return registry


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = build_default_registry(get_settings())
    return _registry
