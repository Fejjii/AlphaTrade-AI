"""HTTP middleware: request-id propagation and structured access logging.

Each request gets a stable ``request_id`` (honoring an inbound header when
present) which is bound to the structlog contextvars so every log line emitted
while handling the request carries it. The id is also echoed back in the
response header for client-side correlation.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.observability.context import set_trace_id

logger = structlog.get_logger("http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind request context, time the request, and emit an access log."""

    def __init__(
        self,
        app,
        *,
        request_id_header: str = "X-Request-ID",
        trace_id_header: str = "X-Trace-ID",
    ) -> None:
        super().__init__(app)
        self._header = request_id_header
        self._trace_header = trace_id_header

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(self._header) or str(uuid.uuid4())
        trace_id = request.headers.get(self._trace_header) or str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        set_trace_id(trace_id)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
            endpoint=request.url.path,
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error("request_failed", latency_ms=elapsed_ms)
            raise
        finally:
            structlog.contextvars.unbind_contextvars("method", "path")

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[self._header] = request_id
        logger.info("request_completed", status_code=response.status_code, latency_ms=elapsed_ms)
        return response
