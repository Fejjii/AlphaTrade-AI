"""Deterministic policies on the existing Telegram pipeline; fake transport only."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.notifications import NotificationPreferencesUpdate
from app.schemas.telegram_policy import (
    AlertPhase,
    NotificationEventType,
    NotificationSeverity,
    TelegramNotificationEvent,
    TelegramNotificationPolicyV2,
)
from app.services.notifications.telegram_policy import PolicyHistory, evaluate_telegram_policy
from app.telegram_security.clock import FrozenClock
from app.telegram_security.contracts import OutboxState
from app.telegram_security.memory import InMemoryTelegramSecurityStore
from app.telegram_security.protocol import TelegramSecurityProtocol
from app.telegram_security.transport import FakeTelegramTransport

NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)
STRATEGY = uuid4()


def event(**changes):
    return TelegramNotificationEvent.model_validate(
        {
            "event_type": "SETUP",
            "severity": "INFO",
            "strategy_id": STRATEGY,
            "symbol": "BTCUSDT",
            "setup_stage": "N3",
            "phase": "CONFIRMED",
            "duplicate_key": "episode-1",
            "occurred_at": NOW,
            **changes,
        }
    )


def reason(policy, **changes):
    return evaluate_telegram_policy(
        TelegramNotificationPolicyV2(**policy), event(**changes), now=NOW
    )


@pytest.mark.parametrize("severity", list(NotificationSeverity))
@pytest.mark.parametrize("minimum", list(NotificationSeverity))
def test_severity_order_is_explicit(severity, minimum):
    ranks = ["INFO", "WATCH", "ACTION", "CRITICAL"]
    blocked = reason({"minimum_severity": minimum}, severity=severity)
    assert (blocked is None) == (ranks.index(severity) >= ranks.index(minimum))


@pytest.mark.parametrize(
    "field,fact",
    [
        ("strategy_subscriptions", STRATEGY),
        ("symbol_subscriptions", "BTCUSDT"),
        ("setup_stages", "N3"),
        ("event_types", "SETUP"),
        ("severities", "INFO"),
    ],
)
def test_subscription_none_empty_and_exact_matching(field, fact):
    assert reason({field: None}) is None
    assert reason({field: []}) == f"POLICY_{field.upper()}"
    assert reason({field: [fact]}) is None


@pytest.mark.parametrize(
    "quality,expected",
    [
        (None, "POLICY_QUALITY_MISSING"),
        ("69.99", "POLICY_MINIMUM_QUALITY"),
        ("70", None),
        ("100", None),
    ],
)
def test_quality_threshold_and_missing_data(quality, expected):
    assert reason({"minimum_quality": "70"}, quality=quality) == expected
    assert reason({"minimum_quality": "0"}, quality=None) == "POLICY_QUALITY_MISSING"


@pytest.mark.parametrize(
    "kind,toggle",
    [
        ("RISK", "risk_alerts"),
        ("PAPER_TRADE_OPENED", "paper_trade_opened"),
        ("PAPER_TRADE_CLOSED", "paper_trade_closed"),
        ("STOP", "stop_event"),
        ("PARTIAL_PROFIT", "partial_profit_event"),
        ("DAILY_REVIEW", "daily_review_event"),
    ],
)
def test_event_toggles(kind, toggle):
    assert reason({toggle: False}, event_type=kind) == "POLICY_EVENT_DISABLED"
    assert reason({toggle: True}, event_type=kind) is None


@pytest.mark.parametrize(
    "phase,toggle", [("FORMING", "forming_alerts"), ("CONFIRMED", "confirmed_alerts")]
)
def test_phase_filters_do_not_change_setup_truth(phase, toggle):
    assert reason({toggle: False}, phase=phase) == f"POLICY_{phase}_DISABLED"


def test_nested_stage_is_exact_and_missing_stage_does_not_match():
    assert reason({"setup_stages": ["N2"]}) == "POLICY_SETUP_STAGES"
    assert reason({"setup_stages": ["N2", "N3"]}) is None
    assert reason({"setup_stages": ["N3"]}, setup_stage=None) == "POLICY_SETUP_STAGES"


@pytest.mark.parametrize(
    "hour,minute,blocked", [(21, 59, False), (22, 0, True), (6, 59, True), (7, 0, False)]
)
def test_overnight_quiet_hours_have_half_open_boundaries(hour, minute, blocked):
    policy = TelegramNotificationPolicyV2(
        quiet_hours={"start": "22:00", "end": "07:00", "timezone": "UTC"}
    )
    result = evaluate_telegram_policy(policy, event(), now=NOW.replace(hour=hour, minute=minute))
    assert (result == "POLICY_QUIET_HOURS") == blocked


def test_quiet_hours_use_iana_timezone_across_dst():
    policy = TelegramNotificationPolicyV2(
        quiet_hours={"start": "02:00", "end": "03:00", "timezone": "Europe/Berlin"}
    )
    for hour in (0, 1):  # Both occurrences of 02:30 during Berlin's fallback.
        assert (
            evaluate_telegram_policy(
                policy, event(), now=datetime(2026, 10, 25, hour, 30, tzinfo=UTC)
            )
            == "POLICY_QUIET_HOURS"
        )


@pytest.mark.parametrize(
    "data",
    [
        {"schema_version": 1},
        {"schema_version": 3},
        {"minimum_severity": "WARNING"},
        {"minimum_quality": "NaN"},
        {"minimum_quality": "Infinity"},
        {"minimum_quality": 101},
        {"cooldown_seconds": -1},
        {"cooldown_seconds": True},
        {"duplicate_suppression_seconds": 604801},
        {"quiet_hours": {"start": "25:00", "end": "07:00"}},
        {"quiet_hours": {"start": "22:00", "end": "22:00"}},
        {"quiet_hours": {"start": "22:00", "end": "07:00", "timezone": "Unknown/Zone"}},
        {"telegram_enabled": True},
        {"bot_token": "forbidden"},
    ],
)
def test_invalid_policy_rejected(data):
    with pytest.raises(ValidationError):
        TelegramNotificationPolicyV2(**data)


def test_mandatory_risk_cannot_be_disabled_by_any_user_filter():
    risk = event(event_type="RISK", mandatory_risk=True)
    policy = TelegramNotificationPolicyV2(
        strategy_subscriptions=(),
        symbol_subscriptions=(),
        setup_stages=(),
        event_types=(),
        severities=(),
        minimum_quality=100,
        risk_alerts=False,
        confirmed_alerts=False,
        cooldown_seconds=600,
        quiet_hours={"start": "00:00", "end": "23:59"},
    )
    assert (
        evaluate_telegram_policy(policy, risk, now=NOW, history=[PolicyHistory(risk, NOW)]) is None
    )
    with pytest.raises(ValidationError):
        event(mandatory_risk=True)


def test_duplicate_and_cooldown_boundaries_including_generator_history():
    policy = TelegramNotificationPolicyV2(cooldown_seconds=120, duplicate_suppression_seconds=60)
    prior = PolicyHistory(event(), NOW)
    for age, expected in [
        (59, "POLICY_DUPLICATE"),
        (60, "POLICY_COOLDOWN"),
        (119, "POLICY_COOLDOWN"),
        (120, None),
    ]:
        assert (
            evaluate_telegram_policy(
                policy, event(), now=NOW + timedelta(seconds=age), history=(h for h in [prior])
            )
            == expected
        )
    assert (
        evaluate_telegram_policy(policy, event(duplicate_key="new"), now=NOW, history=[prior])
        == "POLICY_COOLDOWN"
    )
    for change in (
        {"symbol": "ETHUSDT"},
        {"strategy_id": uuid4()},
        {"setup_stage": "N2"},
        {"phase": AlertPhase.FORMING},
        {"event_type": NotificationEventType.RISK},
    ):
        assert (
            evaluate_telegram_policy(
                policy, event(duplicate_key="new", **change), now=NOW, history=[prior]
            )
            is None
        )


class World:
    def __init__(self):
        self.clock = FrozenClock(NOW)
        self.store = InMemoryTelegramSecurityStore()
        self.transport = FakeTelegramTransport()
        self.policy = TelegramNotificationPolicyV2()
        self.org, self.user, self.binding = uuid4(), uuid4(), uuid4()
        self.protocol = self.restart()

    def restart(self):
        self.protocol = TelegramSecurityProtocol(
            store=self.store,
            transport=self.transport,
            clock=self.clock,
            enabled=True,
            notification_policy_loader=lambda org, user: self.policy,
        )
        return self.protocol

    def enqueue(self, key, notification=None, **changes):
        return self.protocol.enqueue_outbound(
            **{
                "organization_id": self.org,
                "user_id": self.user,
                "binding_id": self.binding,
                "bot_id": "bot",
                "chat_id": "chat",
                "text": "Informational paper alert",
                "idempotency_key": key,
                "notification_event": notification or event(),
                **changes,
            }
        )


def test_duplicate_suppression_survives_restart_and_suppressed_rows_are_never_claimed():
    w = World()
    first = w.enqueue("first")
    w.restart()
    duplicate = w.enqueue("different-transport-key")
    assert duplicate.state == OutboxState.SUPPRESSED
    assert duplicate.last_error == "POLICY_DUPLICATE"
    sent = w.protocol.deliver_pending()
    assert len(sent) == 1 and sent[0].outbox.outbox_id == first.outbox_id
    assert len(w.transport.sent) == 1
    assert w.enqueue("different-transport-key") == duplicate
    assert w.protocol.execution_attempt_count == 0


@pytest.mark.parametrize("field", ["organization_id", "user_id", "binding_id", "bot_id", "chat_id"])
def test_duplicate_history_is_recipient_isolated(field):
    w = World()
    w.enqueue("first")
    changed = uuid4() if field.endswith("_id") and field not in {"bot_id", "chat_id"} else "other"
    assert w.enqueue("other", **{field: changed}).state == OutboxState.PENDING


def test_current_preferences_rechecked_at_delivery_and_suppression_is_terminal():
    w = World()
    row = w.enqueue("first")
    w.policy = TelegramNotificationPolicyV2(setup_stages=("N2",))
    attempts = w.protocol.deliver_pending()
    assert attempts[0].outbox.state == OutboxState.SUPPRESSED
    assert attempts[0].outbox.attempt == 0
    assert attempts[0].error_code == "POLICY_SETUP_STAGES"
    assert w.transport.sent == []
    w.policy = TelegramNotificationPolicyV2()
    assert w.protocol.deliver_pending() == []
    assert w.store.get_outbox(row.outbox_id).state == OutboxState.SUPPRESSED


def test_pre_v2_trader_outbox_cannot_bypass_a_configured_quality_threshold():
    w = World()
    w.protocol.enqueue_outbound(
        organization_id=w.org,
        user_id=w.user,
        bot_id="bot",
        chat_id="chat",
        text="Pre-v2 alert",
        idempotency_key="candidate-alert:legacy",
    )
    w.policy = TelegramNotificationPolicyV2(minimum_quality=0)
    assert w.protocol.deliver_pending()[0].error_code == "POLICY_FACTS_MISSING"
    assert w.transport.sent == []


def test_same_row_delivery_retry_does_not_suppress_itself():
    w = World()
    w.transport.fail_next()
    w.enqueue("first")
    result = w.protocol.deliver_pending()
    assert result[0].outbox.state == OutboxState.RETRYABLE
    w.clock.advance(timedelta(seconds=300))
    w.restart()
    assert w.protocol.deliver_pending()[0].outbox.state == OutboxState.SENT


def test_cooldown_reserves_existing_outbox_admissions():
    w = World()
    w.policy = TelegramNotificationPolicyV2(cooldown_seconds=60)
    w.enqueue("first")
    blocked = w.enqueue("second", event(duplicate_key="new"))
    assert blocked.last_error == "POLICY_COOLDOWN"
    w.clock.advance(timedelta(seconds=60))
    assert w.enqueue("third", event(duplicate_key="newer")).state == OutboxState.PENDING


def test_delayed_send_starts_cooldown_at_actual_delivery_time():
    w = World()
    w.policy = TelegramNotificationPolicyV2(cooldown_seconds=60)
    w.enqueue("first")
    w.clock.advance(timedelta(hours=2))
    sent = w.protocol.deliver_pending()[0].outbox
    assert sent.sent_at == w.clock.now()
    w.restart()
    assert w.enqueue("second", event(duplicate_key="new")).last_error == "POLICY_COOLDOWN"
    w.clock.advance(timedelta(seconds=60))
    assert w.enqueue("third", event(duplicate_key="newer")).state == OutboxState.PENDING


def test_competing_admissions_converge_before_delivery():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    w = World()
    barrier = Barrier(2)

    def admit(key):
        barrier.wait()
        return w.enqueue(key).state

    with ThreadPoolExecutor(max_workers=2) as pool:
        states = list(pool.map(admit, ("one", "two")))
    assert states.count(OutboxState.PENDING) == 1
    assert states.count(OutboxState.SUPPRESSED) == 1
    assert w.transport.sent == []


def test_preferences_serialization_contains_no_activation_or_credentials():
    payload = NotificationPreferencesUpdate(
        telegram_policy={
            "schema_version": 2,
            "minimum_quality": "70.5",
            "setup_stages": ["N2", "N3"],
        }
    )
    stored = payload.telegram_policy.model_dump(mode="json")
    assert TelegramNotificationPolicyV2.model_validate(stored).minimum_quality == Decimal("70.5")
    assert "telegram_enabled" not in stored
    assert "bot_token" not in stored


def test_outbox_policy_facts_roundtrip_and_cannot_change_under_same_identity():
    from app.persistence.telegram_postgres import (
        _outbox_from_row,
        _outbox_to_row,
        _reject_conflicting_outbox_binding,
    )
    from app.telegram_security.errors import TelegramSecurityError

    w = World()
    original = w.enqueue("first", event(quality="75.50"))
    persisted = _outbox_to_row(original)
    restored = _outbox_from_row(persisted)
    assert restored == original
    with pytest.raises(TelegramSecurityError):
        _reject_conflicting_outbox_binding(
            persisted,
            original.model_copy(
                update={
                    "notification_event": event(quality="80"),
                }
            ),
        )
    with pytest.raises(TelegramSecurityError):
        w.enqueue("first", event(quality="80"))


def test_policy_migration_upgrade_downgrade_preserves_terminal_suppression():
    import importlib

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect, text

    migration = importlib.import_module(
        "app.db.migrations.versions.a2tgpolicy002_telegram_policy_v2"
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE user_notification_preferences (id TEXT PRIMARY KEY)"))
        conn.execute(
            text(
                "CREATE TABLE telegram_security_outbox (outbox_id TEXT PRIMARY KEY, "
                "organization_id TEXT, user_id TEXT, bot_id TEXT, chat_id TEXT, "
                "created_at TEXT, state TEXT)"
            )
        )
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        conn.execute(
            text(
                "INSERT INTO telegram_security_outbox (outbox_id, state) "
                "VALUES ('filtered', 'SUPPRESSED')"
            )
        )
        assert "notification_event" in {
            c["name"] for c in inspect(conn).get_columns("telegram_security_outbox")
        }
        with Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
        assert (
            conn.scalar(
                text("SELECT state FROM telegram_security_outbox WHERE outbox_id = 'filtered'")
            )
            == "DEAD_LETTER"
        )
        assert "notification_event" not in {
            c["name"] for c in inspect(conn).get_columns("telegram_security_outbox")
        }
        assert "telegram_policy" not in {
            c["name"] for c in inspect(conn).get_columns("user_notification_preferences")
        }
    engine.dispose()
