"""Project saved demo account evidence without touching order reconciliation."""

import re
from datetime import UTC, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.config import ExchangeMode, ExecutionMode, Settings
from app.core.exchange_safety import is_allowlisted_demo_host
from app.schemas.blofin_sync import BloFinSyncSnapshotItem
from app.schemas.dashboard_demo_account import (
    DashboardDemoAccount,
    DemoAccountBalance,
    DemoAccountPosition,
)

_TOKEN = re.compile(r"^[A-Za-z0-9_/-]{1,64}$")


def demo_account_active(settings: Settings) -> bool:
    if settings.execution_mode is not ExecutionMode.PAPER or settings.enable_real_trading:
        return False
    if not is_allowlisted_demo_host(settings.blofin_demo_rest_base_url):
        return False
    if settings.blofin_readonly_sync_enabled:
        return (
            settings.exchange_mode is ExchangeMode.PAPER_INTERNAL
            and settings.blofin_readonly_configured
        )
    return settings.exchange_demo_active and settings.blofin_demo_configured


def _number(value: Any, *, required: bool = False) -> Decimal | None:
    if value is None or value == "":
        if required:
            raise ValueError("Missing account quantity")
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid account quantity") from exc
    if not result.is_finite():
        raise ValueError("Invalid account quantity")
    return result


def _token(value: Any) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise ValueError("Invalid account instrument")
    return value


def _required_number(value: Any) -> Decimal:
    result = _number(value, required=True)
    assert result is not None
    return result


def project_demo_account(
    snapshot: BloFinSyncSnapshotItem, *, settings: Settings, can_refresh: bool
) -> DashboardDemoAccount:
    synced_at = snapshot.synced_at
    if synced_at.tzinfo is None:
        synced_at = synced_at.replace(tzinfo=UTC)
    base = DashboardDemoAccount(
        status="unavailable",
        can_refresh=can_refresh,
        snapshot_id=snapshot.id,
        synced_at=synced_at,
        expires_at=synced_at + timedelta(seconds=settings.blofin_sync_stale_after_seconds),
        message="The latest demo account sync failed. Refresh to retrieve current account data.",
    )
    if (
        snapshot.health_status.value == "unavailable"
        or snapshot.provider != "blofin_demo"
        or snapshot.exchange_mode
        not in {
            ExchangeMode.PAPER_EXCHANGE_DEMO.value,
            ExchangeMode.PAPER_INTERNAL.value,
        }
        or snapshot.provenance.get("read_only") is not True
        or snapshot.provenance.get("order_mutations") is not False
    ):
        return base
    try:
        balance_rows = snapshot.account_snapshot.get("balances")
        position_rows = snapshot.positions_snapshot.get("items")
        if not isinstance(balance_rows, list) or not isinstance(position_rows, list):
            raise ValueError("Missing account rows")
        balances: list[DemoAccountBalance] = []
        positions: list[DemoAccountPosition] = []
        for row in balance_rows[: settings.blofin_sync_max_balances]:
            if not isinstance(row, dict):
                raise ValueError("Invalid balance row")
            balances.append(
                DemoAccountBalance(
                    asset=_token(row.get("asset")),
                    total=_required_number(row.get("total")),
                    available=_required_number(row.get("available")),
                )
            )
        for row in position_rows[: settings.blofin_sync_max_positions]:
            if not isinstance(row, dict):
                raise ValueError("Invalid position row")
            size = _required_number(row.get("size"))
            if size == 0:
                continue
            side = row.get("side")
            if side == "net":
                side = "long" if size > 0 else "short"
            if side not in {"long", "short"}:
                raise ValueError("Unknown position side")
            positions.append(
                DemoAccountPosition(
                    symbol=_token(row.get("symbol")),
                    side=side,
                    contracts=abs(size),
                    entry_price=_number(row.get("entry_price")),
                    mark_price=_number(row.get("mark_price")),
                    unrealized_pnl=_number(row.get("unrealized_pnl")),
                    leverage=_number(row.get("leverage")),
                )
            )
    except (ValueError, InvalidOperation):
        base.message = "Demo account evidence is incomplete. Refresh to retrieve current data."
        return base
    base.balances = balances
    base.positions = positions
    base.balances_truncated = snapshot.account_snapshot.get("balances_truncated") is True or len(
        balance_rows
    ) > len(balances)
    base.positions_truncated = (
        snapshot.positions_snapshot.get("truncated") is True
        or len(position_rows) > settings.blofin_sync_max_positions
    )
    base.position_count = None if base.positions_truncated else len(positions)
    base.status = "stale" if snapshot.is_stale else snapshot.health_status.value
    base.message = (
        "Saved demo account snapshot is stale. Refresh for current balances and positions."
        if base.status == "stale"
        else "Native demo account snapshot. Positions may include trades placed outside AlphaTrade."
    )
    return base
