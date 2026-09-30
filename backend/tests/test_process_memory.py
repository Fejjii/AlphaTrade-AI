"""Platform RSS units and current-versus-peak sampling regressions."""

import subprocess
from types import SimpleNamespace

import pytest

from app.observability import process_memory as memory


def test_linux_proc_values_are_kib(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(memory, "_proc_status_kb", lambda: (4096, 8192))
    sample = memory.read_process_memory()
    assert sample.rss_bytes == 4096 * 1024
    assert sample.peak_rss_bytes == 8192 * 1024


def test_darwin_current_rss_is_distinct_from_peak_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(memory, "_proc_status_kb", lambda: (None, None))
    monkeypatch.setattr(memory.sys, "platform", "darwin")
    monkeypatch.setattr(memory, "_darwin_rss_kb", lambda: 4096)
    monkeypatch.setattr(memory.resource, "getrusage", lambda _: SimpleNamespace(ru_maxrss=8388608))
    sample = memory.read_process_memory()
    assert sample.rss_bytes == 4194304
    assert sample.peak_rss_bytes == 8388608


def test_darwin_ps_reports_current_kib(monkeypatch: pytest.MonkeyPatch) -> None:
    def run(args: list[str], **kwargs: object) -> SimpleNamespace:
        assert args == ["/bin/ps", "-o", "rss=", "-p", str(memory.os.getpid())]
        assert kwargs["timeout"] == 1
        assert kwargs["check"] is True
        return SimpleNamespace(stdout="  4096\n")

    monkeypatch.setattr(memory.subprocess, "run", run)
    assert memory._darwin_rss_kb() == 4096


def test_darwin_ps_failure_keeps_peak_units(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="ps", timeout=1)

    monkeypatch.setattr(memory, "_proc_status_kb", lambda: (None, None))
    monkeypatch.setattr(memory.sys, "platform", "darwin")
    monkeypatch.setattr(memory.subprocess, "run", unavailable)
    monkeypatch.setattr(memory.resource, "getrusage", lambda _: SimpleNamespace(ru_maxrss=8388608))
    sample = memory.read_process_memory()
    assert sample.rss_bytes == sample.peak_rss_bytes == 8388608
