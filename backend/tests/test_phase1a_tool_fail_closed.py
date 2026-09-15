"""Phase 1A slice 3 — mutation/execution tools cannot fake success."""

from __future__ import annotations

from app.core.config import Settings
from app.tools.fail_closed import ToolFailureCode
from app.tools.registry import build_default_registry


def test_paper_execution_never_reports_success() -> None:
    registry = build_default_registry(Settings(log_json=False))
    output = registry.execute("paper_execution", {"mode": "paper", "symbol": "BTCUSDT"})
    assert output.success is False
    assert output.error is not None
    assert ToolFailureCode.NOT_IMPLEMENTED.value in output.error
    assert output.result is not None
    assert output.result.get("code") == ToolFailureCode.NOT_IMPLEMENTED.value
    assert output.result.get("status") != "mock"


def test_journal_writer_never_reports_success() -> None:
    registry = build_default_registry(Settings(log_json=False))
    output = registry.execute("journal_writer", {"text": "wrote a journal"})
    assert output.success is False
    assert output.error is not None
    assert ToolFailureCode.NOT_IMPLEMENTED.value in output.error


def test_scenario_simulator_never_reports_success() -> None:
    registry = build_default_registry(Settings(log_json=False))
    output = registry.execute("scenario_simulator", {})
    assert output.success is False
    assert output.error is not None
    assert ToolFailureCode.UNAVAILABLE.value in output.error


def test_stub_execute_helper_is_gone() -> None:
    import app.tools.registry as registry_mod

    assert not hasattr(registry_mod, "_stub_execute")
