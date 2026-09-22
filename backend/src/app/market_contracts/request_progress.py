"""Progress hook for long read-only market requests.

The Watcher binds a lease heartbeat here while evidence is assembled. Adapters
call :func:`notify_market_request_progress` between pages and during backoff.
The hook must not mint a Candidate or send an order.
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token

ProgressHook = Callable[[], None]

_HOOK: ContextVar[ProgressHook | None] = ContextVar("market_request_progress", default=None)


def bind_market_request_progress(hook: ProgressHook) -> Token[ProgressHook | None]:
    """Install ``hook`` for the current context. Reset with the returned token."""

    return _HOOK.set(hook)


def reset_market_request_progress(token: Token[ProgressHook | None]) -> None:
    _HOOK.reset(token)


def notify_market_request_progress() -> None:
    """Invoke the bound hook. Missing hooks are a no-op."""

    hook = _HOOK.get()
    if hook is None:
        return
    hook()
