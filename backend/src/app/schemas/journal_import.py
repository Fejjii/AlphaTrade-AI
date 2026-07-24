"""Bulk journal import schemas (AT-033 — Journal Completion).

Import is record-only: rows become canonical ``journal_trades`` with
``source=imported`` and ``entry_method=import``. Requests carry raw row
objects so validation failures are reported per row (reconciliation UX)
instead of rejecting the whole request. Commits are all-or-nothing in one
unit of work; the ``external_ref`` dedup (explicit or fingerprint-derived)
makes re-runs idempotent, which is the recovery model for failed imports.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import (
    JournalImportBatchStatus,
    JournalTradeStatus,
    ORMModel,
    StrictModel,
    Symbol,
    Timeframe,
    TradeDirection,
    TradeResult,
)

# Bounded request size: keeps validation, dedup lookups, and the batch row
# report cheap and predictable. Larger histories import in multiple requests.
MAX_IMPORT_ROWS = 500


class JournalImportMode(StrEnum):
    """Import execution mode: preview (default) or all-or-nothing commit."""

    DRY_RUN = "dry_run"
    COMMIT = "commit"


class JournalImportRowOutcome(StrEnum):
    """Per-row reconciliation outcome."""

    CREATED = "created"  # commit mode: row persisted
    WOULD_CREATE = "would_create"  # dry-run mode: row valid and new
    DUPLICATE = "duplicate"  # (org, external_ref) already exists or repeats in batch
    INVALID = "invalid"  # validation failed; blocks commit


class JournalImportRow(StrictModel):
    """One historical trade to import.

    Internal record links (positions, strategies, setups) are intentionally
    excluded: imported history references external systems, and linking is a
    manual enrichment step after import. ``external_ref`` is optional — rows
    without one get a deterministic fingerprint so re-imports stay idempotent.
    """

    symbol: Symbol
    timeframe: Timeframe
    direction: TradeDirection
    status: JournalTradeStatus = JournalTradeStatus.CLOSED
    exchange: str | None = Field(default=None, max_length=40)
    strategy_label: str | None = Field(default=None, max_length=120)
    entry_price: Decimal | None = Field(default=None, gt=0)
    entry_time: datetime | None = None
    exit_price: Decimal | None = Field(default=None, gt=0)
    exit_time: datetime | None = None
    exit_reason: str | None = Field(default=None, max_length=60)
    size: Decimal | None = Field(default=None, gt=0)
    leverage: Decimal | None = Field(default=None, gt=0)
    fees: Decimal | None = None
    funding: Decimal | None = None
    slippage: Decimal | None = None
    gross_pnl: Decimal | None = None
    net_pnl: Decimal | None = None
    result: TradeResult = TradeResult.OPEN
    notes: str | None = Field(default=None, max_length=8000)
    tags: list[str] = Field(default_factory=list)
    external_ref: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def _validate_window(self) -> JournalImportRow:
        if (
            self.entry_time is not None
            and self.exit_time is not None
            and self.exit_time < self.entry_time
        ):
            raise ValueError("exit_time must not be before entry_time")
        return self


class JournalImportRequest(StrictModel):
    """Bulk import request. Rows are raw objects validated individually."""

    mode: JournalImportMode = JournalImportMode.DRY_RUN
    source_label: str | None = Field(default=None, max_length=120)
    rows: list[dict[str, Any]] = Field(min_length=1, max_length=MAX_IMPORT_ROWS)


class JournalImportRowResult(StrictModel):
    """Reconciliation outcome for one submitted row."""

    index: int
    outcome: JournalImportRowOutcome
    external_ref: str | None = None
    # Created trade id (commit) or the pre-existing trade id (duplicate).
    journal_trade_id: UUID | None = None
    errors: list[str] = Field(default_factory=list)


class JournalImportResult(StrictModel):
    """Batch summary plus per-row outcomes.

    ``committed=False`` in commit mode means validation blocked the
    all-or-nothing commit and nothing was persisted; fix the invalid rows and
    re-run (duplicates are skipped idempotently).
    """

    mode: JournalImportMode
    committed: bool
    batch_id: UUID | None = None
    total_rows: int
    created_count: int
    duplicate_count: int
    invalid_count: int
    results: list[JournalImportRowResult]


class JournalImportBatchRead(ORMModel):
    """Persisted import batch (reconciliation history)."""

    id: UUID
    organization_id: UUID
    user_id: UUID
    status: JournalImportBatchStatus
    source_label: str | None = None
    total_rows: int
    created_count: int
    duplicate_count: int
    invalid_count: int
    row_report: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class PaginatedJournalImportBatches(StrictModel):
    items: list[JournalImportBatchRead]
    total: int
    limit: int
    offset: int
