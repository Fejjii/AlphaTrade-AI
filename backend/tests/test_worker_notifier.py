"""Tests for worker system alerts: severity, quiet hours, summary, no inbound."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import Settings
from app.db.models import MarketScanRun
from app.main import create_app
from app.providers.alert_delivery.base import AlertDeliveryPayload, AlertDeliveryResult
from app.schemas.common import AlertDeliveryChannel, PaperAlertSeverity, PaperAlertType
from app.workers.notifier import WorkerNotifier, in_quiet_hours, passes_min_severity
from app.workers.summary import aggregate_daily_summary


class _FakeTelegram:
    channel = AlertDeliveryChannel.TELEGRAM

    def __init__(self) -> None:
        self.payloads: list[AlertDeliveryPayload] = []

    def is_enabled(self) -> bool:
        return True

    def deliver(self, payload: AlertDeliveryPayload) -> AlertDeliveryResult:
        self.payloads.append(payload)
        return AlertDeliveryResult(success=True, channel=self.channel)


def _settings(**overrides) -> Settings:
    base = {
        "worker_alerts_enabled": True,
        "alert_delivery_enabled": True,
        "telegram_alerts_enabled": True,
        "telegram_bot_token": "token",
        "telegram_chat_id": "12345",
    }
    base.update(overrides)
    return Settings(**base)


# --- pure helpers ----------------------------------------------------------


def test_passes_min_severity() -> None:
    assert passes_min_severity(PaperAlertSeverity.INFO, "info") is True
    assert passes_min_severity(PaperAlertSeverity.INFO, "warning") is False
    assert passes_min_severity(PaperAlertSeverity.CRITICAL, "warning") is True


def test_in_quiet_hours_normal_window() -> None:
    now = datetime(2026, 1, 1, 23, 30, tzinfo=UTC)
    assert in_quiet_hours(now, "22:00", "23:59") is True
    assert in_quiet_hours(now, "08:00", "17:00") is False


def test_in_quiet_hours_wraps_midnight() -> None:
    assert in_quiet_hours(datetime(2026, 1, 1, 2, 0, tzinfo=UTC), "22:00", "06:00") is True
    assert in_quiet_hours(datetime(2026, 1, 1, 12, 0, tzinfo=UTC), "22:00", "06:00") is False


def test_in_quiet_hours_disabled_when_unset() -> None:
    assert in_quiet_hours(datetime(2026, 1, 1, 2, 0, tzinfo=UTC), "", "") is False


# --- daily summary ---------------------------------------------------------


def test_aggregate_daily_summary() -> None:
    runs = [
        MarketScanRun(
            worker_name="w",
            status="success",
            symbols_scanned=3,
            setups_detected=2,
            started_at=datetime.now(UTC),
        ),
        MarketScanRun(
            worker_name="w",
            status="failed",
            symbols_scanned=0,
            setups_detected=0,
            started_at=datetime.now(UTC),
        ),
    ]
    summary = aggregate_daily_summary(runs)
    assert summary.total_cycles == 2
    assert summary.successful_cycles == 1
    assert summary.failed_cycles == 1
    assert summary.symbols_scanned == 3
    assert summary.setups_detected == 2
    assert "daily summary" in summary.to_message().lower()


# --- notifier --------------------------------------------------------------


def test_notifier_disabled_by_default() -> None:
    fake = _FakeTelegram()
    notifier = WorkerNotifier(Settings(), providers=[fake])
    assert notifier.notify_setup_detected(count=2) is False
    assert fake.payloads == []


def test_notifier_delivers_when_enabled() -> None:
    fake = _FakeTelegram()
    notifier = WorkerNotifier(_settings(), providers=[fake])
    assert notifier.notify_setup_detected(count=2) is True
    assert len(fake.payloads) == 1
    assert "no trade executed" in fake.payloads[0].message.lower()


def test_notifier_respects_min_severity() -> None:
    fake = _FakeTelegram()
    notifier = WorkerNotifier(_settings(worker_alert_min_severity="warning"), providers=[fake])
    # INFO setup alert is below the warning floor.
    assert notifier.notify_setup_detected(count=1) is False
    # A warning-level worker error passes.
    assert notifier.notify_worker_error("boom") is True


def test_notifier_quiet_hours_blocks_info_but_not_critical() -> None:
    fake = _FakeTelegram()
    quiet_now = lambda: datetime(2026, 1, 1, 3, 0, tzinfo=UTC)  # noqa: E731
    notifier = WorkerNotifier(
        _settings(worker_quiet_hours_start="00:00", worker_quiet_hours_end="06:00"),
        providers=[fake],
        clock=quiet_now,
    )
    assert notifier.notify_setup_detected(count=1) is False  # info during quiet hours
    assert (
        notifier.notify(
            alert_type=PaperAlertType.STOP_HIT,
            severity=PaperAlertSeverity.CRITICAL,
            message="critical",
        )
        is True
    )


# --- safety: no inbound telegram path --------------------------------------


def test_no_inbound_telegram_route_exists() -> None:
    app = create_app(settings=Settings())
    paths = {getattr(route, "path", "") for route in app.routes}
    assert not any("telegram" in path.lower() for path in paths)
