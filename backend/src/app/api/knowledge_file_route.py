"""Bound multipart bytes and upload time before Starlette parses/spools a file."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, Response
from fastapi.routing import APIRoute
from starlette.types import Message

from app.core.errors import ValidationAppError
from app.rag.file_import_worker import MAX_FILE_BYTES

MAX_MULTIPART_BYTES = MAX_FILE_BYTES + 64 * 1024


class KnowledgeFileRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()
        if not self.path.endswith(("/files/preview", "/files/import")):
            return original

        async def bounded(request: Request) -> Response:
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    too_large = int(content_length) > MAX_MULTIPART_BYTES
                except ValueError as exc:
                    raise ValidationAppError("Invalid upload content length.") from exc
                if too_large:
                    raise ValidationAppError(
                        "Upload exceeds the 5 MiB file limit.", status_code=413
                    )
            chunks: list[bytes] = []
            size = 0
            try:
                async with asyncio.timeout(10):
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > MAX_MULTIPART_BYTES:
                            raise ValidationAppError(
                                "Upload exceeds the 5 MiB file limit.", status_code=413
                            )
                        chunks.append(chunk)
            except TimeoutError as exc:
                raise ValidationAppError("Upload exceeded the ten-second time limit.") from exc
            body = b"".join(chunks)
            sent = False

            async def receive() -> Message:
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await request.receive()

            return await original(Request(request.scope, receive=receive))

        return bounded
