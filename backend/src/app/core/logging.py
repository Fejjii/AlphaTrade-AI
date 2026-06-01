"""Structured logging setup using structlog.

Logs are emitted as JSON in non-local environments for ingestion by log
pipelines, and as a human-friendly console format locally. A ``request_id`` and
other contextual fields are bound per-request via :mod:`app.core.middleware`.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.guardrails.redaction import redact_for_log


def _redact_sensitive(_logger: object, _name: str, event_dict: dict) -> dict:
    """structlog processor delegating to guardrails redaction."""
    return redact_for_log(event_dict)


def configure_logging(*, log_level: str = "INFO", json_logs: bool = True) -> None:
    """Configure stdlib logging and structlog.

    Args:
        log_level: Minimum level name (e.g. ``"INFO"``).
        json_logs: Emit JSON when True, console-formatted output otherwise.
    """
    level = logging.getLevelNamesMapping().get(log_level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact_sensitive,
        structlog.processors.StackInfoRenderer(),
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger, optionally namespaced."""
    return structlog.get_logger(name)
