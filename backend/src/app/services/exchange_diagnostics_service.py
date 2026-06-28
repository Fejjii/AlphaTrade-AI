"""Read-only exchange demo diagnostics for operator dashboards."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from app.core.config import ExchangeMode, ExecutionMode, Settings
from app.core.demo_order_status import probe_demo_order_status_with_retry
from app.core.errors import ExchangeDemoInactiveError, ExchangeProviderError
from app.core.exchange_demo_access import (
    get_demo_account_provider,
    get_demo_execution_provider,
)
from app.core.exchange_readiness import exchange_provider_status
from app.guardrails.redaction import redact_text
from app.providers.base import ProviderHealth
from app.providers.exchange.errors import ExchangeError
from app.providers.exchange.mapping import to_blofin_inst_id
from app.providers.registry import ProviderRegistry
from app.schemas.common import AuditEventType
from app.services.audit_service import AuditService

ReadinessLevel = Literal["ready", "degraded", "blocked"]

KNOWN_POSITION_MODES = frozenset({"net_mode", "long_short_mode"})
DEFAULT_INST_ID = "BTC-USDT"
DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_MARGIN_MODE = "cross"
MIRROR_EVENT_TYPES = (
    AuditEventType.EXCHANGE_DEMO_ORDER_CREATED,
    AuditEventType.EXCHANGE_DEMO_ORDER_FAILED,
)


def _redact_operator_message(message: str, settings: Settings) -> str:
    """Redact secret-like substrings before exposing mirror errors to operators."""
    redacted = redact_text(message)
    for secret in (
        settings.blofin_api_key,
        settings.blofin_api_secret,
        settings.blofin_api_passphrase,
    ):
        token = secret.strip()
        if token and token in redacted:
            redacted = redacted.replace(token, "***REDACTED***")
    return redacted[:200]


@dataclass
class InstrumentProbe:
    symbol: str = DEFAULT_SYMBOL
    inst_id: str = DEFAULT_INST_ID
    active: bool | None = None
    probe_ok: bool = False


@dataclass
class LeverageProbe:
    inst_id: str = DEFAULT_INST_ID
    margin_mode: str = DEFAULT_MARGIN_MODE
    leverage: Decimal | None = None
    probe_ok: bool = False


@dataclass
class DiagnosticsSnapshot:
    exchange_mode: str
    execution_mode: str
    real_trading_enabled: bool
    demo_active: bool
    provider_health: str | None
    worker_enabled: bool
    telegram_enabled: bool
    position_mode: str | None = None
    leverage: LeverageProbe | None = None
    instrument: InstrumentProbe | None = None
    venue_positions_count: int | None = None
    last_exchange_order_status: str | None = None
    last_demo_mirror_result: str | None = None
    last_demo_mirror_error_code: str | None = None
    last_demo_mirror_error_message: str | None = None
    last_cancel_status: str | None = None
    readiness: ReadinessLevel = "blocked"
    warnings: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def compute_readiness(
    *,
    settings: Settings,
    provider_health: str | None,
    position_mode: str | None,
    instrument: InstrumentProbe | None,
    leverage: LeverageProbe | None,
    venue_positions_count: int | None,
    order_status_probe_ok: bool,
    last_demo_mirror_result: str | None,
    warnings: list[str],
) -> ReadinessLevel:
    """Derive operator readiness from posture and probe results."""
    if settings.real_trading_enabled:
        return "blocked"
    if settings.exchange_mode is not ExchangeMode.PAPER_EXCHANGE_DEMO:
        return "blocked"
    if settings.execution_mode is not ExecutionMode.PAPER:
        return "blocked"
    if provider_health == ProviderHealth.UNAVAILABLE.value:
        return "blocked"
    if venue_positions_count is not None and venue_positions_count > 0:
        return "blocked"
    if instrument is not None and instrument.probe_ok and instrument.active is False:
        return "blocked"
    if position_mode is not None and position_mode not in KNOWN_POSITION_MODES:
        return "blocked"
    if not settings.exchange_demo_active:
        return "blocked"

    degraded = False
    if leverage is not None and not leverage.probe_ok:
        degraded = True
    if not order_status_probe_ok:
        degraded = True
    if provider_health == ProviderHealth.DEGRADED.value:
        degraded = True
    if last_demo_mirror_result == "failed":
        degraded = True
    if any("transient" in warning.lower() for warning in warnings):
        degraded = True

    if degraded:
        return "degraded"

    if (
        settings.execution_mode is ExecutionMode.PAPER
        and not settings.real_trading_enabled
        and settings.exchange_demo_active
        and provider_health == ProviderHealth.HEALTHY.value
        and instrument is not None
        and instrument.probe_ok
        and instrument.active is True
        and leverage is not None
        and leverage.probe_ok
        and venue_positions_count == 0
        and position_mode in KNOWN_POSITION_MODES
    ):
        return "ready"

    return "degraded"


def _latest_mirror_audit(
    audit_service: AuditService,
    *,
    organization_id: uuid.UUID,
) -> tuple[AuditEventType | None, dict[str, object]]:
    latest_type: AuditEventType | None = None
    latest_meta: dict[str, object] = {}
    latest_ts: datetime | None = None

    for event_type in MIRROR_EVENT_TYPES:
        records, total = audit_service.list_records(
            organization_id=organization_id,
            event_type=event_type,
            limit=1,
        )
        if total == 0 or not records:
            continue
        record = records[0]
        if latest_ts is None or record.timestamp > latest_ts:
            latest_ts = record.timestamp
            latest_type = event_type
            latest_meta = dict(record.redacted_metadata or {})

    return latest_type, latest_meta


def _latest_cancel_audit(
    audit_service: AuditService,
    *,
    organization_id: uuid.UUID,
) -> str | None:
    records, total = audit_service.list_records(
        organization_id=organization_id,
        event_type=AuditEventType.EXCHANGE_DEMO_ORDER_CANCELLED,
        limit=1,
    )
    if total == 0 or not records:
        return None
    return "cancelled"


def build_exchange_diagnostics_summary(
    *,
    settings: Settings,
    registry: ProviderRegistry,
    audit_service: AuditService,
    organization_id: uuid.UUID,
) -> DiagnosticsSnapshot:
    """Aggregate redacted exchange demo diagnostics for operators."""
    generated_at = datetime.now(UTC)
    warnings: list[str] = []
    provider = exchange_provider_status(registry)
    provider_health = provider.health.value if provider is not None else None

    snapshot = DiagnosticsSnapshot(
        exchange_mode=settings.exchange_mode.value,
        execution_mode=settings.execution_mode.value,
        real_trading_enabled=settings.real_trading_enabled,
        demo_active=settings.exchange_demo_active,
        provider_health=provider_health,
        worker_enabled=settings.worker_enabled,
        telegram_enabled=settings.telegram_alerts_enabled,
        generated_at=generated_at,
    )

    if settings.real_trading_enabled:
        warnings.append("Real trading is enabled — demo exchange is blocked.")
        snapshot.warnings = warnings
        snapshot.readiness = "blocked"
        return snapshot

    mirror_type, mirror_meta = _latest_mirror_audit(
        audit_service,
        organization_id=organization_id,
    )
    if mirror_type is AuditEventType.EXCHANGE_DEMO_ORDER_CREATED:
        snapshot.last_demo_mirror_result = "created"
    elif mirror_type is AuditEventType.EXCHANGE_DEMO_ORDER_FAILED:
        snapshot.last_demo_mirror_result = "failed"
        code = mirror_meta.get("venue_error_code")
        message = mirror_meta.get("venue_error_message")
        if isinstance(code, str):
            snapshot.last_demo_mirror_error_code = code
        if isinstance(message, str):
            snapshot.last_demo_mirror_error_message = _redact_operator_message(message, settings)

    snapshot.last_cancel_status = _latest_cancel_audit(
        audit_service,
        organization_id=organization_id,
    )

    order_status_probe_ok = True
    if not settings.exchange_demo_active:
        warnings.append("Exchange demo mode is not active.")
        snapshot.warnings = warnings
        snapshot.readiness = compute_readiness(
            settings=settings,
            provider_health=provider_health,
            position_mode=None,
            instrument=None,
            leverage=None,
            venue_positions_count=None,
            order_status_probe_ok=True,
            last_demo_mirror_result=snapshot.last_demo_mirror_result,
            warnings=warnings,
        )
        return snapshot

    try:
        account = get_demo_account_provider(settings)
    except ExchangeDemoInactiveError:
        warnings.append("BloFin demo exchange probes unavailable.")
        snapshot.warnings = warnings
        snapshot.readiness = compute_readiness(
            settings=settings,
            provider_health=provider_health,
            position_mode=None,
            instrument=None,
            leverage=None,
            venue_positions_count=None,
            order_status_probe_ok=True,
            last_demo_mirror_result=snapshot.last_demo_mirror_result,
            warnings=warnings,
        )
        return snapshot

    instrument = InstrumentProbe()
    try:
        instruments = account.get_instruments()
        normalized = DEFAULT_SYMBOL.upper()
        match = next((i for i in instruments if i.symbol.upper() == normalized), None)
        if match is None:
            warnings.append(f"Instrument {DEFAULT_SYMBOL} not found on demo venue.")
        else:
            instrument.symbol = match.symbol
            instrument.inst_id = match.inst_id
            instrument.active = match.active
            instrument.probe_ok = True
    except ExchangeError as exc:
        warnings.append("Instrument probe failed (transient venue error).")
        instrument.probe_ok = False
        _ = redact_text(str(exc))[:200]
    snapshot.instrument = instrument

    leverage = LeverageProbe()
    try:
        info = account.get_leverage_info(inst_id=DEFAULT_INST_ID, margin_mode=DEFAULT_MARGIN_MODE)
        leverage.inst_id = info.inst_id
        leverage.margin_mode = info.margin_mode
        leverage.leverage = info.leverage
        leverage.probe_ok = True
    except ExchangeError:
        warnings.append("Leverage probe failed.")
        leverage.probe_ok = False
    snapshot.leverage = leverage

    position_mode: str | None = None
    try:
        mode = account.get_position_mode()
        position_mode = mode.position_mode
        snapshot.position_mode = position_mode
    except ExchangeError:
        warnings.append("Position mode probe failed.")
        position_mode = None

    venue_positions_count: int | None = None
    try:
        positions = account.get_positions()
        venue_positions_count = len(positions)
        snapshot.venue_positions_count = venue_positions_count
        if venue_positions_count > 0:
            warnings.append("Open venue positions detected — resolve before demo trading.")
    except ExchangeError:
        warnings.append("Venue positions probe failed (transient venue error).")
        venue_positions_count = None

    exchange_order_id = mirror_meta.get("exchange_order_id")
    inst_id = mirror_meta.get("inst_id")
    if (
        mirror_type is AuditEventType.EXCHANGE_DEMO_ORDER_CREATED
        and isinstance(exchange_order_id, str)
        and exchange_order_id
        and isinstance(inst_id, str)
        and inst_id
    ):
        try:
            execution = get_demo_execution_provider(settings)
            normalized_inst = to_blofin_inst_id(inst_id) if "-" not in inst_id else inst_id.upper()

            def get_order():
                return execution.get_order(
                    inst_id=normalized_inst,
                    exchange_order_id=exchange_order_id,
                )

            result = probe_demo_order_status_with_retry(get_order)
            snapshot.last_exchange_order_status = result.status
        except (ExchangeError, ExchangeProviderError):
            order_status_probe_ok = False
            warnings.append("Last mirrored order status probe failed.")

    snapshot.warnings = warnings
    snapshot.readiness = compute_readiness(
        settings=settings,
        provider_health=provider_health,
        position_mode=position_mode,
        instrument=instrument,
        leverage=leverage,
        venue_positions_count=venue_positions_count,
        order_status_probe_ok=order_status_probe_ok,
        last_demo_mirror_result=snapshot.last_demo_mirror_result,
        warnings=warnings,
    )
    return snapshot
