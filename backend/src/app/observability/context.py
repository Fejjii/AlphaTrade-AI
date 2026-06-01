"""Request and trace context for structured observability."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("obs_user_id", default=None)
_organization_id: ContextVar[str | None] = ContextVar("obs_organization_id", default=None)


def get_or_create_trace_id() -> str:
    """Return the current trace id, creating one if absent."""
    current = _trace_id.get()
    if current:
        return current
    new_id = str(uuid.uuid4())
    _trace_id.set(new_id)
    return new_id


def set_trace_id(trace_id: str) -> None:
    _trace_id.set(trace_id)


def bind_identity(*, user_id: str | None, organization_id: str | None) -> None:
    if user_id:
        _user_id.set(user_id)
    if organization_id:
        _organization_id.set(organization_id)


def get_bound_identity() -> tuple[str | None, str | None]:
    return _user_id.get(), _organization_id.get()


def clear_observability_context() -> None:
    _trace_id.set(None)
    _user_id.set(None)
    _organization_id.set(None)
