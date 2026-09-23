"""Structured logging setup using structlog.

Logs are emitted as JSON in non-local environments for ingestion by log
pipelines, and as a human-friendly console format locally. A ``request_id`` and
other contextual fields are bound per-request via :mod:`app.core.middleware`.
"""

from __future__ import annotations

import logging
import sys
import traceback
from typing import Any, cast

import structlog
from structlog.typing import EventDict, Processor

from app.guardrails.redaction import redact_for_log, redact_text


class SecretRedactionFilter(logging.Filter):
    """Redact secrets in stdlib log records, including httpx URL lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        args = record.args
        if isinstance(args, tuple):
            record.args = tuple(
                redact_text(item) if isinstance(item, str) else item for item in args
            )
        elif isinstance(args, dict):
            record.args = {
                key: redact_text(value) if isinstance(value, str) else value
                for key, value in args.items()
            }
        return True


class RedactingFormatter(logging.Formatter):
    """Formatter that redacts the rendered line and any traceback."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))

    def formatException(self, ei: logging._SysExcInfoType) -> str:  # noqa: N802
        return redact_text(super().formatException(ei))


def _redact_sensitive(_logger: object, _name: str, event_dict: EventDict) -> EventDict:
    """structlog processor. Exception text is redacted before it is rendered."""
    event: dict[str, Any] = redact_for_log(dict(event_dict))
    exc_info = event.get("exc_info")
    if not exc_info:
        return event
    if isinstance(exc_info, BaseException):
        text = "".join(traceback.format_exception(exc_info))
    elif isinstance(exc_info, tuple) and exc_info[0] is not None:
        text = "".join(traceback.format_exception(*exc_info))
    else:
        text = str(exc_info)
    event["exception"] = redact_text(text)
    event.pop("exc_info", None)
    return event


def _install_stdlib_redaction(level: int) -> None:
    """Keep application logs at ``level``. Quiet httpx/httpcore URL logs."""

    redaction_filter = SecretRedactionFilter()
    formatter = RedactingFormatter("%(message)s")
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.addFilter(redaction_filter)
        root.addHandler(handler)
    else:
        for existing in root.handlers:
            if not any(isinstance(item, SecretRedactionFilter) for item in existing.filters):
                existing.addFilter(redaction_filter)
            if not isinstance(existing.formatter, RedactingFormatter):
                existing.setFormatter(formatter)
    for name in ("httpx", "httpcore"):
        library = logging.getLogger(name)
        library.setLevel(logging.WARNING)
        if not any(isinstance(item, SecretRedactionFilter) for item in library.filters):
            library.addFilter(redaction_filter)


def configure_logging(*, log_level: str = "INFO", json_logs: bool = True) -> None:
    """Configure stdlib logging and structlog.

    Args:
        log_level: Minimum level name (e.g. ``"INFO"``).
        json_logs: Emit JSON when True, console-formatted output otherwise.
    """
    level = logging.getLevelNamesMapping().get(log_level.upper(), logging.INFO)
    _install_stdlib_redaction(level)

    shared_processors: list[Processor] = [
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
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
