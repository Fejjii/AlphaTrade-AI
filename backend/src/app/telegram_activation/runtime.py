"""Paper Telegram process. Drains the outbox and polls. It does not mint Candidates.

The Watcher only enqueues. This process is the delivery and inbound authority.
Staging inbound is polling. Two replicas share one Postgres lease so they do
not double-send. A lost process resumes from the durable cursor and outbox.
"""

from __future__ import annotations

import signal
import threading
from dataclasses import dataclass
from types import FrameType
from uuid import UUID, uuid4

import structlog
from sqlalchemy.orm import Session, sessionmaker

from app.controlled_activation.profile import (
    controlled_telegram_projection,
    telegram_enrollment_runtime,
)
from app.core.config import Settings
from app.persistence.runtime_status import (
    TELEGRAM_COMPONENT,
    RuntimeStatusWrite,
    publish_runtime_status,
    try_acquire_runtime_lease,
)
from app.runtime_safety.paper_actions import (
    automated_paper_actions_blocked,
    read_kill_switch_active,
    read_process_kill_switch,
)
from app.telegram_activation.controller import TelegramPaperActivation
from app.telegram_activation.cursor import ActivationCursorStore, enrollment_cursor_owner
from app.telegram_activation.errors import TelegramActivationError
from app.telegram_activation.intake import ParsedTelegramUpdate, TelegramUpdateSource
from app.telegram_security.clock import Clock, SystemClock
from app.telegram_security.contracts import ChatType, MessageIdentity, TelegramInboundUpdate
from app.telegram_security.errors import TelegramSecurityError
from app.telegram_security.protocol import TelegramSecurityProtocol
from app.telegram_security.transport import TransportSendResult

logger = structlog.get_logger("telegram_activation.runtime")

_LEASE_TTL_SECONDS = 30


@dataclass(frozen=True, slots=True)
class TelegramRuntimeCycle:
    """One drain/poll pass. Counts are zero when the kill switch pauses actions."""

    posture: str
    delivered: int
    poll_applied: int
    poll_rejected: int
    kill_switch_active: bool
    lease_held: bool
    last_error_code: str


class _NoSend:
    """Transport placeholder. Enrollment does not send from this object."""

    def send_private_message(
        self,
        *,
        bot_id: str,
        chat_id: str,
        text: str,
        idempotency_key: str,
    ) -> TransportSendResult:
        del bot_id, chat_id, text, idempotency_key
        return TransportSendResult(ok=False, retryable=False, error_code="NETWORK_DISABLED")


def resolve_telegram_posture(settings: Settings) -> str:
    """``projection``, ``enrollment``, or ``disarmed``. Webhook is never selected."""

    if controlled_telegram_projection(settings):
        return "projection"
    if telegram_enrollment_runtime(settings):
        return "enrollment"
    return "disarmed"


class TelegramPaperRuntime:
    """Durable paper Telegram loop. Advisory only."""

    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: sessionmaker[Session],
        clock: Clock,
        worker_id: str,
        posture: str,
        controller: TelegramPaperActivation | None = None,
        protocol: TelegramSecurityProtocol | None = None,
        update_source: TelegramUpdateSource | None = None,
        cursor_store: ActivationCursorStore | None = None,
        bot_id: str = "",
        startup_error: str = "",
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._clock = clock
        self._worker_id = worker_id
        self._posture = posture
        self._controller = controller
        self._protocol = protocol
        self._source = update_source
        self._cursors = cursor_store
        self._bot_id = bot_id.strip() or settings.telegram_bot_id.strip()
        self._startup_error = startup_error
        self._stop = threading.Event()
        self._poll_seconds = float(settings.watcher_paper_poll_interval_seconds)

    @property
    def posture(self) -> str:
        return self._posture

    @property
    def worker_id(self) -> str:
        return self._worker_id

    def stop(self) -> None:
        self._stop.set()

    def run_forever(self) -> int:
        def _handle(_signum: int, _frame: FrameType | None) -> None:
            self.stop()

        signal.signal(signal.SIGINT, _handle)
        signal.signal(signal.SIGTERM, _handle)
        cycles = 0
        self._stop.clear()
        while not self._stop.is_set():
            try:
                self.run_cycle()
            except Exception:
                logger.error("telegram_paper_cycle_error", worker_id=self._worker_id)
            cycles += 1
            self._stop.wait(self._poll_seconds)
        return cycles

    def run_cycle(self) -> TelegramRuntimeCycle:
        """Deliver due outbox rows, then poll. Kill switch pauses both."""

        now = self._clock.now()
        try:
            held = try_acquire_runtime_lease(
                self._session_factory,
                component=TELEGRAM_COMPONENT,
                owner=self._worker_id,
                now=now,
                ttl_seconds=_LEASE_TTL_SECONDS,
            )
        except Exception:
            held = False
        killed = self._kill_switch_active()
        delivered = 0
        applied = 0
        rejected = 0
        last_error = self._startup_error
        if not held:
            last_error = last_error or "lease_held_elsewhere"
        elif killed:
            last_error = "kill_switch_active"
        elif self._posture == "projection" and self._controller is not None:
            delivered, applied, rejected, last_error = self._projection_pass()
        elif self._posture == "enrollment":
            applied, rejected, last_error = self._enrollment_pass()
        cycle = TelegramRuntimeCycle(
            posture=self._posture,
            delivered=delivered,
            poll_applied=applied,
            poll_rejected=rejected,
            kill_switch_active=killed,
            lease_held=held,
            last_error_code=last_error,
        )
        self._publish(cycle)
        return cycle

    def _projection_pass(self) -> tuple[int, int, int, str]:
        assert self._controller is not None
        attempts = self._controller.deliver(limit=10)
        delivered = sum(1 for item in attempts if item.accepted)
        last_error = ""
        for item in attempts:
            if not item.accepted and item.error_code:
                last_error = item.error_code
        poll = self._controller.poll_once(limit=20)
        return delivered, poll.applied, poll.rejected, last_error

    def _enrollment_pass(self) -> tuple[int, int, str]:
        if self._protocol is None or self._source is None or self._cursors is None:
            return 0, 0, "polling_source_disabled"
        if not self._bot_id:
            return 0, 0, "bot_unconfigured"
        cursor = self._cursors.get_cursor(bot_id=self._bot_id)
        offset = None if cursor is None else cursor.last_update_id + 1
        try:
            batch = self._source.fetch(offset=offset, limit=20)
        except TelegramActivationError as exc:
            return 0, 0, exc.reason
        applied = 0
        rejected = 0
        last_error = ""
        for update in batch:
            if update.update_id <= 0:
                rejected += 1
                continue
            organization_id = self._complete_enrollment(update)
            if organization_id is None:
                rejected += 1
                last_error = last_error or "enrollment_not_completed"
            else:
                applied += 1
            self._advance(
                update,
                organization_id=organization_id,
                cursor_owner=_cursor_owner(cursor),
            )
        return applied, rejected, last_error

    def _complete_enrollment(self, update: ParsedTelegramUpdate) -> UUID | None:
        if self._protocol is None:
            return None
        if update.kind != "message" or update.chat_type is not ChatType.PRIVATE:
            return None
        if not update.text.strip() or not update.telegram_user_id or not update.message_id:
            return None
        try:
            result = self._protocol.complete_enrollment(
                token=update.text.strip(),
                identity=MessageIdentity(
                    bot_id=self._bot_id,
                    telegram_user_id=update.telegram_user_id,
                    chat_id=update.chat_id,
                    chat_type=update.chat_type,
                    update_id=update.update_id,
                    message_id=update.message_id,
                ),
                inbound=TelegramInboundUpdate(update_type="message", body_size=update.body_size),
            )
        except TelegramSecurityError:
            return None
        return result.binding.organization_id

    def _advance(
        self,
        update: ParsedTelegramUpdate,
        *,
        organization_id: UUID | None,
        cursor_owner: UUID | None,
    ) -> None:
        from app.persistence.telegram_activation import advance_bot_cursor

        owner = organization_id or cursor_owner or enrollment_cursor_owner(self._bot_id)
        advance_bot_cursor(
            self._session_factory,
            bot_id=self._bot_id,
            organization_id=owner,
            update_id=update.update_id,
            now=self._clock.now(),
        )

    def _kill_switch_active(self) -> bool:
        try:
            with self._session_factory() as session:
                if self._controller is not None:
                    active = read_kill_switch_active(
                        session,
                        self._settings,
                        self._controller.recipient_organization_id,
                    )
                else:
                    active = read_process_kill_switch(session, self._settings)
        except Exception:
            return True
        return automated_paper_actions_blocked(active)

    def _publish(self, cycle: TelegramRuntimeCycle) -> None:
        pending, retryable, dead = self._outbox_counts()
        state = "paused" if cycle.kill_switch_active else self._posture
        try:
            publish_runtime_status(
                self._session_factory,
                RuntimeStatusWrite(
                    component=TELEGRAM_COMPONENT,
                    worker_id=self._worker_id,
                    heartbeat_at=self._clock.now(),
                    activation_state=_activation_state(cycle),
                    lease_owner=self._worker_id if cycle.lease_held else "",
                    fence_held=cycle.lease_held,
                    telegram_runtime_state=state,
                    inbound_mode=self._settings.telegram_inbound_mode.value,
                    outbox_pending=pending,
                    outbox_retryable=retryable,
                    outbox_dead_letter=dead,
                    last_delivery_at=self._clock.now() if cycle.delivered else None,
                    last_error_code=cycle.last_error_code,
                    kill_switch_active=cycle.kill_switch_active,
                    # try_acquire_runtime_lease already committed the fence.
                    # Publishing must not zero the epoch or steal another owner.
                    preserve_lease=True,
                ),
            )
        except Exception:
            logger.warning("telegram_runtime_status_unpublished", worker_id=self._worker_id)

    def _outbox_counts(self) -> tuple[int, int, int]:
        if self._controller is None:
            return 0, 0, 0
        counts = self._controller.preflight().outbox
        if counts is None:
            return 0, 0, 0
        return counts.pending, counts.retryable, counts.dead_letter


def _cursor_owner(cursor: object | None) -> UUID | None:
    organization_id = getattr(cursor, "organization_id", None)
    if isinstance(organization_id, UUID):
        return organization_id
    return None


def _activation_state(cycle: TelegramRuntimeCycle) -> str:
    if not cycle.lease_held:
        return "lease_held_elsewhere"
    if cycle.kill_switch_active:
        return "monitoring"
    if cycle.posture == "disarmed":
        return "disarmed"
    if cycle.last_error_code in {"recipient_binding_missing", "polling_source_disabled"}:
        return "refused"
    return "running"


def build_telegram_runtime(
    settings: Settings,
    session_factory: sessionmaker[Session],
    *,
    transport: object | None = None,
    update_source: TelegramUpdateSource | None = None,
    clock: Clock | None = None,
    worker_id: str | None = None,
) -> TelegramPaperRuntime:
    """Compose the paper Telegram process. Does not place orders."""

    from app.telegram_security.transport import TelegramTransport

    resolved_clock = clock if clock is not None else SystemClock()
    resolved_worker = worker_id or f"telegram-paper:{uuid4().hex[:16]}"
    resolved_transport = transport if isinstance(transport, TelegramTransport) else None
    posture = resolve_telegram_posture(settings)
    if posture == "projection":
        from app.controlled_activation.projection import build_controlled_scan_hook

        try:
            projection = build_controlled_scan_hook(
                settings,
                session_factory,
                transport=resolved_transport,
                update_source=update_source,
                clock=resolved_clock,
            )
        except TelegramActivationError as exc:
            return TelegramPaperRuntime(
                settings=settings,
                session_factory=session_factory,
                clock=resolved_clock,
                worker_id=resolved_worker,
                posture="projection",
                startup_error=exc.reason,
            )
        if projection is None:
            posture = "disarmed"
        else:
            return TelegramPaperRuntime(
                settings=settings,
                session_factory=session_factory,
                clock=resolved_clock,
                worker_id=resolved_worker,
                posture="projection",
                controller=projection.controller,
            )
    if posture == "enrollment":
        protocol, source, cursors = _enrollment_parts(
            settings,
            session_factory,
            clock=resolved_clock,
            transport=resolved_transport,
            update_source=update_source,
        )
        return TelegramPaperRuntime(
            settings=settings,
            session_factory=session_factory,
            clock=resolved_clock,
            worker_id=resolved_worker,
            posture="enrollment",
            protocol=protocol,
            update_source=source,
            cursor_store=cursors,
        )
    return TelegramPaperRuntime(
        settings=settings,
        session_factory=session_factory,
        clock=resolved_clock,
        worker_id=resolved_worker,
        posture="disarmed",
    )


def _enrollment_parts(
    settings: Settings,
    session_factory: sessionmaker[Session],
    *,
    clock: Clock,
    transport: object | None,
    update_source: TelegramUpdateSource | None,
) -> tuple[TelegramSecurityProtocol, TelegramUpdateSource | None, ActivationCursorStore]:
    from app.controlled_activation.projection import _update_source
    from app.persistence.composition import build_postgres_telegram_security_store
    from app.persistence.telegram_activation import PostgresActivationCursorStore
    from app.telegram_activation.policy import PAPER_ACTIVATION_BACKOFF
    from app.telegram_security.transport import TelegramTransport

    store = build_postgres_telegram_security_store(session_factory)
    resolved_transport: TelegramTransport = (
        transport if isinstance(transport, TelegramTransport) else _NoSend()
    )
    protocol = TelegramSecurityProtocol(
        store=store,
        transport=resolved_transport,
        clock=clock,
        enabled=True,
        retry_backoff=PAPER_ACTIVATION_BACKOFF,
    )
    source = update_source if update_source is not None else _update_source(settings)
    return protocol, source, PostgresActivationCursorStore(session_factory)
