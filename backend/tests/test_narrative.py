"""Slice 21 — LLM narrative layer, validation, and evaluation tests."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.agents.response_builder import build_trading_analysis
from app.agents.runtime import AgentRuntime
from app.core.config import Settings
from app.guardrails.narrative_validation import NarrativeValidationGuardrail
from app.guardrails.testing import TEST_INVALID_NARRATIVE, TEST_UNSAFE_NARRATIVE
from app.providers.llm import MockLLMProvider
from app.schemas.agent import AgentState, Intent
from app.schemas.analysis import TradingAnalysisDetail
from app.schemas.common import RiskSeverity
from app.schemas.narrative import TradingNarrativeDetail
from app.services.agent_service import AgentInvokeContext, AgentService
from app.services.narrative_service import NarrativeService, build_sanitized_narrative_context
from app.services.risk_service import RiskService
from app.services.strategy_service import StrategyService
from app.strategies.registry import build_default_registry
from app.tools.registry import build_default_registry as build_tools


def _context() -> AgentInvokeContext:
    return AgentInvokeContext(
        request_id="narr-test-001",
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        organization_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
    )


def _service(**kwargs: object) -> AgentService:
    defaults = {
        "log_json": False,
        "provider_mode": "mock",
        "market_data_provider": "mock",
        "narrative_llm_enabled": True,
        "openai_api_key": "",
    }
    defaults.update(kwargs)  # type: ignore[arg-type]
    settings = Settings(**defaults)
    runtime = AgentRuntime(
        settings=settings,
        risk_service=RiskService(),
        strategy_service=StrategyService(registry=build_default_registry()),
        tool_registry=build_tools(settings),
    )
    return AgentService(runtime=runtime)


def _sample_analysis(**overrides: object) -> TradingAnalysisDetail:
    base = {
        "summary": "Trade proposal for BTCUSDT.",
        "setup_type": "htf_trend_pullback",
        "evidence": ["RSI 55.0"],
        "risk_level": RiskSeverity.MEDIUM,
        "confidence": 0.72,
        "invalidation": "Close below stop.",
        "stop_loss_or_no_trade_reason": "Stop loss at 58000.",
        "approval_status": "pending",
        "next_decision_point": "Submit for approval.",
        "paper_mode_disclaimer": "Paper mode only.",
        "market_data_quality": "mock",
    }
    base.update(overrides)
    return TradingAnalysisDetail.model_validate(base)


def test_narrative_schema_forbids_extra_fields() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TradingNarrativeDetail.model_validate(
            {
                "summary": "x",
                "setup_interpretation": "x",
                "evidence_explanation": "x",
                "risk_explanation": "x",
                "invalidation_explanation": "x",
                "next_decision_point": "x",
                "caution_notes": [],
                "limitations": [],
                "paper_mode_disclaimer": "x",
                "citations_used": [],
                "place_order_now": True,
            }
        )


def test_mock_llm_narrative_path() -> None:
    provider = MockLLMProvider()
    service = NarrativeService(llm_provider=provider, llm_model="gpt-4o-mini")
    agent = AgentState(request_id="r1", message="analyze btc")
    analysis = _sample_analysis()
    result = service.enhance(agent, analysis)
    assert result.narrative.summary
    assert result.metadata.provider == "mock-llm"
    combined = result.narrative.summary.lower() + " ".join(result.narrative.limitations).lower()
    assert "mock" in combined


def test_missing_openai_key_uses_mock() -> None:
    settings = Settings(openai_api_key="", log_json=False)
    from app.providers.factory import resolve_providers

    resolved = resolve_providers(settings)
    assert resolved.llm.name == "mock-llm"


def test_invalid_llm_output_fallback() -> None:
    response = _service().run(f"analyze btc {TEST_INVALID_NARRATIVE}", _context())
    assert response.narrative_meta is not None
    assert response.narrative_meta.source == "deterministic_fallback"
    assert response.narrative is not None


def test_unsafe_llm_output_fallback() -> None:
    response = _service().run(f"analyze btc {TEST_UNSAFE_NARRATIVE}", _context())
    assert response.narrative_meta is not None
    assert response.narrative_meta.source == "deterministic_fallback"
    assert "guaranteed profit" not in response.reply.lower()


def test_guardrail_rejects_unsafe_narrative_text() -> None:
    validator = NarrativeValidationGuardrail()
    outcome = validator.evaluate_text("Guaranteed profit if you go all in now.")
    assert outcome.blocked


def test_narrative_preserves_risk_level_in_explanation() -> None:
    response = _service().run("plan btc pullback", _context(), symbol="BTCUSDT")
    assert response.narrative is not None
    assert "medium" in response.narrative.risk_explanation.lower() or (
        response.analysis
        and response.analysis.risk_level
        and response.analysis.risk_level.value in response.reply.lower()
    )


def test_narrative_preserves_approval_status() -> None:
    response = _service().run(
        "plan trade BTC [test_low_confidence]",
        _context(),
        symbol="BTCUSDT",
    )
    assert response.approval_status == "pending"
    assert response.narrative is not None
    combined = response.reply.lower()
    assert "pending" in combined or "approval" in combined


def test_narrative_no_execution_status_change() -> None:
    response = _service().run("analyze btc", _context())
    lowered = response.reply.lower()
    assert "executed on exchange" not in lowered
    assert "order placed live" not in lowered


def test_mock_data_warning_in_narrative() -> None:
    response = _service().run("analyze btc", _context())
    assert response.analysis is not None
    assert response.analysis.market_data_quality == "mock"
    assert "mock" in response.reply.lower()


def test_usage_event_for_narrative_call() -> None:
    response = _service().run("analyze eth", _context())
    assert response.narrative_meta is not None
    assert response.usage is not None


def test_sanitized_context_excludes_secrets() -> None:
    agent = AgentState(
        request_id="r1",
        message="password=secret token=abc",
        organization_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
    )
    ctx = build_sanitized_narrative_context(agent, _sample_analysis())
    raw = json.dumps(ctx)
    assert "secret" not in raw.lower() or "password" in raw  # excerpt only user message slice


def test_deterministic_fallback_when_narrative_disabled() -> None:
    response = _service(narrative_llm_enabled=False).run("analyze btc", _context())
    assert response.narrative_meta is not None
    assert response.narrative_meta.source == "deterministic_fallback"


def test_prompt_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in (
        "trading_analysis_narrative.txt",
        "risk_explanation.txt",
        "journal_review_coach.txt",
    ):
        assert (root / "prompts" / name).is_file()


def test_journal_review_prompt_selected() -> None:
    service = NarrativeService(llm_provider=MockLLMProvider(), llm_model="gpt-4o-mini")
    agent = AgentState(request_id="r1", message="review journal", intent=Intent.REVIEW)
    assert service.select_prompt_name(agent) == "journal_review_coach"


def test_build_trading_analysis_authority_unchanged() -> None:
    from app.agents.runtime import AgentRuntime

    settings = Settings(log_json=False)
    runtime = AgentRuntime(
        settings=settings,
        risk_service=RiskService(),
        strategy_service=StrategyService(registry=build_default_registry()),
        tool_registry=build_tools(settings),
    )
    agent = AgentState(
        request_id="r1",
        message="analyze",
        intent=Intent.PLAN_TRADE,
        market_data_quality="mock",
    )
    detail = build_trading_analysis(agent, runtime)
    assert detail.market_data_quality == "mock"
