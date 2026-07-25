"""TradingView signal intake schemas (AT-037 — paper-only)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import TradingViewSignalStatus

CREATE_TRADINGVIEW_CANDIDATE_CONFIRM = "CREATE_TRADINGVIEW_PAPER_CANDIDATE"

_MAX_SOURCE_KEYS = 20
_MAX_SOURCE_STRING = 256
_MAX_METADATA_DEPTH = 2


class TradingViewSignalWebhookPayload(BaseModel):
    """Strict inbound TradingView webhook body (bounded field sizes)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    organization_id: uuid.UUID
    alert_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=30)
    timeframe: str = Field(min_length=1, max_length=10)
    direction: Literal["long", "short"]
    setup_name: str | None = Field(default=None, max_length=120)
    setup_version: int | None = Field(default=None, ge=1, le=10_000)
    strategy_id: uuid.UUID | None = None
    strategy_version_id: uuid.UUID | None = None
    trigger_level: float | None = Field(default=None, ge=0, le=1e12)
    invalidation_level: float | None = Field(default=None, ge=0, le=1e12)
    take_profit_level: float | None = Field(default=None, ge=0, le=1e12)
    stop_loss_level: float | None = Field(default=None, ge=0, le=1e12)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    source: dict[str, Any] | None = None
    occurred_at: datetime | None = None
    backtest_run_id: uuid.UUID | None = None
    journal_trade_id: uuid.UUID | None = None

    @field_validator("symbol", "timeframe", "alert_id", "setup_name", "idempotency_key")
    @classmethod
    def _reject_control_chars(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if any(ord(ch) < 32 for ch in value):
            raise ValueError("Control characters are not allowed.")
        return value

    @field_validator("source")
    @classmethod
    def _bound_source(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        if len(value) > _MAX_SOURCE_KEYS:
            raise ValueError(f"source may contain at most {_MAX_SOURCE_KEYS} keys.")
        return _bound_metadata(value, depth=0)

    @model_validator(mode="after")
    def _default_idempotency(self) -> TradingViewSignalWebhookPayload:
        if self.idempotency_key is None:
            object.__setattr__(self, "idempotency_key", self.alert_id)
        return self


def _bound_metadata(value: dict[str, Any], *, depth: int) -> dict[str, Any]:
    if depth > _MAX_METADATA_DEPTH:
        raise ValueError("source nesting is too deep.")
    out: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or len(key) > 64:
            raise ValueError("source keys must be strings of length <= 64.")
        if isinstance(item, str):
            if len(item) > _MAX_SOURCE_STRING:
                raise ValueError(f"source string values must be <= {_MAX_SOURCE_STRING} chars.")
            out[key] = item
        elif isinstance(item, bool | int | float):
            out[key] = item
        elif item is None:
            out[key] = None
        elif isinstance(item, dict):
            out[key] = _bound_metadata(item, depth=depth + 1)
        elif isinstance(item, list):
            if len(item) > 20:
                raise ValueError("source lists may contain at most 20 items.")
            bounded_list: list[Any] = []
            for entry in item:
                if isinstance(entry, str):
                    if len(entry) > _MAX_SOURCE_STRING:
                        raise ValueError("source list strings are too long.")
                    bounded_list.append(entry)
                elif entry is None or isinstance(entry, bool | int | float):
                    bounded_list.append(entry)
                else:
                    raise ValueError("source lists may only contain scalars.")
            out[key] = bounded_list
        else:
            raise ValueError("Unsupported source value type.")
    return out


class TradingViewSignalLinks(BaseModel):
    setup_definition_id: uuid.UUID | None = None
    strategy_id: uuid.UUID | None = None
    strategy_version_id: uuid.UUID | None = None
    source_alert_id: uuid.UUID | None = None
    draft_id: uuid.UUID | None = None
    candidate_id: uuid.UUID | None = None
    journal_trade_id: uuid.UUID | None = None
    backtest_run_id: uuid.UUID | None = None
    paper_candidate_path: str | None = None
    strategy_path: str | None = None
    journal_path: str | None = None


class TradingViewSignalItem(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    external_alert_id: str
    idempotency_key: str
    status: TradingViewSignalStatus
    symbol: str
    timeframe: str
    direction: str
    setup_name: str | None = None
    setup_version: int | None = None
    setup_definition_id: uuid.UUID | None = None
    strategy_id: uuid.UUID | None = None
    strategy_version_id: uuid.UUID | None = None
    trigger_level: float | None = None
    invalidation_level: float | None = None
    take_profit_level: float | None = None
    stop_loss_level: float | None = None
    confidence: float | None = None
    source_metadata: dict[str, Any] | None = None
    validation_errors: list[str] | None = None
    rejection_reason: str | None = None
    received_at: datetime
    validated_at: datetime | None = None
    occurred_at: datetime | None = None
    duplicate_of_signal_id: uuid.UUID | None = None
    links: TradingViewSignalLinks
    note: str = "Advisory TradingView intake only. Never creates live orders."


class TradingViewSignalIntakeResult(BaseModel):
    signal: TradingViewSignalItem
    already_exists: bool = False
    duplicate: bool = False


class TradingViewSignalListResponse(BaseModel):
    items: list[TradingViewSignalItem]
    total: int
    limit: int
    offset: int


class TradingViewSignalCreateCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: str = Field(min_length=1, max_length=80)


class TradingViewSignalCreateCandidateResult(BaseModel):
    signal: TradingViewSignalItem
    candidate_id: uuid.UUID
    draft_id: uuid.UUID
    source_alert_id: uuid.UUID
    already_exists: bool = False
    note: str = (
        "Paper-validation candidate only. Does not authorize real trading or place exchange orders."
    )
