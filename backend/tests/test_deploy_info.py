"""Tests for deploy metadata helpers."""

from __future__ import annotations

from app.core.deploy_info import resolve_git_sha


def test_resolve_git_sha_prefers_git_sha_env(monkeypatch) -> None:
    monkeypatch.setenv("GIT_SHA", "abc1234")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "def5678")
    assert resolve_git_sha() == "abc1234"


def test_resolve_git_sha_falls_back_to_render(monkeypatch) -> None:
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "089739b")
    assert resolve_git_sha() == "089739b"


def test_resolve_git_sha_none_when_unset(monkeypatch) -> None:
    for key in ("GIT_SHA", "RENDER_GIT_COMMIT", "SOURCE_VERSION"):
        monkeypatch.delenv(key, raising=False)
    assert resolve_git_sha() is None
