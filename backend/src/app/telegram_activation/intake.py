"""Webhook and polling intake. Group chats and unknown update types are rejected."""

from __future__ import annotations

import json
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.telegram_activation.contracts import InboundSourceKind
from app.telegram_activation.errors import TelegramActivationError
from app.telegram_activation.transport import HttpPoster
from app.telegram_security.actions import MAX_INBOUND_UPDATE_BYTES
from app.telegram_security.contracts import ChatType
from app.telegram_security.hashing import hash_secret, secrets_equal

_ALLOWED_CHAT = "private"


class ParsedTelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    update_id: int = Field(ge=0)
    body_size: int = Field(ge=0)
    kind: Literal["message", "callback_query", "rejected"]
    chat_type: ChatType = ChatType.PRIVATE
    chat_id: str = ""
    telegram_user_id: str = ""
    message_id: str | None = None
    text: str = ""
    callback_query_id: str | None = None
    callback_data: str | None = None
    rejection: str | None = None


class TelegramUpdateSource(Protocol):
    @property
    def kind(self) -> InboundSourceKind: ...

    def fetch(self, *, offset: int | None, limit: int) -> tuple[ParsedTelegramUpdate, ...]: ...


class RefusingTelegramUpdateSource:
    """Polling default. It does not call getUpdates."""

    @property
    def kind(self) -> InboundSourceKind:
        return InboundSourceKind.REFUSING

    def fetch(self, *, offset: int | None, limit: int) -> tuple[ParsedTelegramUpdate, ...]:
        del offset, limit
        raise TelegramActivationError(
            "Telegram network polling is disabled.",
            reason="network_disabled",
        )


class RecordedUpdateSource:
    """Explicit in-process update fixture. This is not a live Telegram poll."""

    def __init__(
        self, updates: tuple[ParsedTelegramUpdate, ...] | list[ParsedTelegramUpdate]
    ) -> None:
        self._updates = tuple(updates)

    @property
    def kind(self) -> InboundSourceKind:
        return InboundSourceKind.RECORDED

    def fetch(self, *, offset: int | None, limit: int) -> tuple[ParsedTelegramUpdate, ...]:
        rows = [row for row in self._updates if offset is None or row.update_id >= offset]
        return tuple(rows[:limit])


class HttpTelegramUpdateSource:
    """getUpdates client. Refuses unless network_permitted is true."""

    def __init__(
        self,
        *,
        token: str,
        timeout_seconds: float,
        network_permitted: bool,
        http_post: HttpPoster | None = None,
    ) -> None:
        self._token = token.strip()
        self._timeout = timeout_seconds
        self._permitted = network_permitted and bool(self._token)
        self._http_post = http_post if http_post is not None else httpx.post

    @property
    def kind(self) -> InboundSourceKind:
        if self._permitted:
            return InboundSourceKind.HTTP
        return InboundSourceKind.REFUSING

    def fetch(self, *, offset: int | None, limit: int) -> tuple[ParsedTelegramUpdate, ...]:
        if not self._permitted:
            raise TelegramActivationError(
                "Telegram network polling is disabled.",
                reason="network_disabled",
            )
        body: dict[str, object] = {
            "limit": limit,
            "timeout": 0,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            body["offset"] = offset
        try:
            response = self._http_post(
                f"https://api.telegram.org/bot{self._token}/getUpdates",
                json=body,
                timeout=self._timeout,
            )
        except Exception as exc:
            raise TelegramActivationError(
                "Telegram getUpdates failed.",
                reason="transport_failure",
            ) from exc
        payload = _json_body(response)
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise TelegramActivationError(
                "Telegram getUpdates was rejected.",
                reason="transport_rejected",
            )
        result = payload.get("result")
        if not isinstance(result, list):
            raise TelegramActivationError(
                "Telegram getUpdates result was not a list.",
                reason="invalid_update",
            )
        parsed: list[ParsedTelegramUpdate] = []
        for item in result:
            raw = json.dumps(item, separators=(",", ":")).encode("utf-8")
            parsed.append(parse_telegram_update(item, body_size=len(raw)))
        return tuple(parsed)


def secret_matches(*, configured: str, presented: str | None) -> bool:
    """Constant-time compare of secret hashes. Empty configured secrets never match."""
    if not configured or presented is None or not presented:
        return False
    return secrets_equal(hash_secret(configured), hash_secret(presented))


def parse_telegram_update(payload: object, *, body_size: int) -> ParsedTelegramUpdate:
    """Parse one Telegram update. Rejected rows are permanent and carry no authority."""
    if body_size > MAX_INBOUND_UPDATE_BYTES:
        return _rejected(update_id=0, body_size=body_size, reason="update_too_large")
    if not isinstance(payload, dict):
        return _rejected(update_id=0, body_size=body_size, reason="invalid_update")
    update_id = payload.get("update_id")
    if not isinstance(update_id, int) or isinstance(update_id, bool) or update_id < 0:
        return _rejected(update_id=0, body_size=body_size, reason="invalid_update")
    has_message = "message" in payload
    has_callback = "callback_query" in payload
    if has_message == has_callback:
        return _rejected(update_id=update_id, body_size=body_size, reason="update_type_rejected")
    if has_message:
        return _parse_message(payload["message"], update_id=update_id, body_size=body_size)
    return _parse_callback(payload["callback_query"], update_id=update_id, body_size=body_size)


def parse_webhook_body(raw: bytes) -> ParsedTelegramUpdate:
    if len(raw) > MAX_INBOUND_UPDATE_BYTES:
        return _rejected(update_id=0, body_size=len(raw), reason="update_too_large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _rejected(update_id=0, body_size=len(raw), reason="invalid_update")
    return parse_telegram_update(payload, body_size=len(raw))


def _parse_message(message: object, *, update_id: int, body_size: int) -> ParsedTelegramUpdate:
    if not isinstance(message, dict):
        return _rejected(update_id=update_id, body_size=body_size, reason="invalid_update")
    chat_id, chat_type, chat_reason = _chat(message.get("chat"))
    user_id = _actor_id(message.get("from"))
    message_id = _actor_id(message.get("message_id"))
    text = message.get("text", "")
    if chat_reason is not None:
        return _rejected(update_id=update_id, body_size=body_size, reason=chat_reason)
    if chat_id is None or user_id is None or message_id is None or not isinstance(text, str):
        return _rejected(update_id=update_id, body_size=body_size, reason="invalid_update")
    if len(text.encode("utf-8")) > 4096:
        return _rejected(update_id=update_id, body_size=body_size, reason="message_too_large")
    return ParsedTelegramUpdate(
        update_id=update_id,
        body_size=body_size,
        kind="message",
        chat_type=chat_type or ChatType.PRIVATE,
        chat_id=chat_id,
        telegram_user_id=user_id,
        message_id=message_id,
        text=text,
    )


def _parse_callback(callback: object, *, update_id: int, body_size: int) -> ParsedTelegramUpdate:
    if not isinstance(callback, dict):
        return _rejected(update_id=update_id, body_size=body_size, reason="invalid_update")
    message = callback.get("message")
    chat_source = message if isinstance(message, dict) else callback
    chat_id, chat_type, chat_reason = _chat(
        chat_source.get("chat") if isinstance(chat_source, dict) else None
    )
    user_id = _actor_id(callback.get("from"))
    callback_id = callback.get("id")
    data = callback.get("data")
    if chat_reason is not None:
        return _rejected(update_id=update_id, body_size=body_size, reason=chat_reason)
    if (
        chat_id is None
        or user_id is None
        or not isinstance(callback_id, str)
        or not callback_id
        or len(callback_id) > 128
        or not isinstance(data, str)
        or not data
        or len(data) > 64
    ):
        return _rejected(update_id=update_id, body_size=body_size, reason="invalid_update")
    return ParsedTelegramUpdate(
        update_id=update_id,
        body_size=body_size,
        kind="callback_query",
        chat_type=chat_type or ChatType.PRIVATE,
        chat_id=chat_id,
        telegram_user_id=user_id,
        callback_query_id=callback_id,
        callback_data=data,
    )


def _chat(value: object) -> tuple[str | None, ChatType | None, str | None]:
    if not isinstance(value, dict):
        return None, None, "invalid_update"
    chat_id = _actor_id(value.get("id"))
    raw_type = value.get("type")
    if chat_id is None or not isinstance(raw_type, str):
        return None, None, "invalid_update"
    if raw_type != _ALLOWED_CHAT:
        return chat_id, None, "chat_not_private"
    return chat_id, ChatType.PRIVATE, None


def _actor_id(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
    else:
        return None
    if not text or len(text) > 64:
        return None
    return text


def _rejected(*, update_id: int, body_size: int, reason: str) -> ParsedTelegramUpdate:
    return ParsedTelegramUpdate(
        update_id=update_id,
        body_size=body_size,
        kind="rejected",
        rejection=reason,
    )


def _json_body(response: object) -> object:
    reader = getattr(response, "json", None)
    if not callable(reader):
        return None
    try:
        return reader()
    except Exception:
        return None
