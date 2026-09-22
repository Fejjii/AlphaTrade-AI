"""Observability emitters and trace context.

Submodule imports must not pull the agent graph. Eager exports here previously
cycled ``metrics`` → emitters → agents → emitters and blocked a cold
``python -m app.workers.watcher_paper`` start.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ObservabilityEmitter",
    "bind_identity",
    "get_or_create_trace_id",
    "set_trace_id",
]


def __getattr__(name: str) -> Any:
    if name == "ObservabilityEmitter":
        from app.observability.emitters import ObservabilityEmitter

        return ObservabilityEmitter
    if name in {"bind_identity", "get_or_create_trace_id", "set_trace_id"}:
        from app.observability import context

        return getattr(context, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
