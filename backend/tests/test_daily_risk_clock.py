"""The authoritative risk day follows the caller's clock and user timezone."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.risk.daily_risk_accounting import DailyRiskAccounting


@pytest.mark.parametrize(
    ("moment", "timezone", "expected"),
    [
        (datetime(2024, 2, 29, 23, 30, tzinfo=UTC), "UTC", date(2024, 2, 29)),
        (datetime(2024, 2, 29, 23, 30, tzinfo=UTC), "Europe/Berlin", date(2024, 3, 1)),
        (datetime(2030, 1, 1, 0, 30, tzinfo=UTC), "America/New_York", date(2029, 12, 31)),
        (datetime(2026, 10, 25, 0, 30, tzinfo=UTC), "Europe/Berlin", date(2026, 10, 25)),
        (datetime(2026, 10, 25, 1, 30, tzinfo=UTC), "Europe/Berlin", date(2026, 10, 25)),
        (datetime(2030, 1, 1, 0, 30, tzinfo=UTC), "invalid/zone", date(2030, 1, 1)),
    ],
)
def test_injected_clock_resolves_risk_day(moment, timezone, expected, monkeypatch):
    class NoWallClock(datetime):
        @classmethod
        def now(cls, tz=None):
            pytest.fail("Injected daily risk accounting must never read wall time")

    monkeypatch.setattr("app.services.risk.daily_risk_accounting.datetime", NoWallClock)
    settings = SimpleNamespace(get=lambda **_: SimpleNamespace(timezone=timezone))
    accounting = DailyRiskAccounting(None, settings, clock=lambda: moment)
    day, zone = accounting.resolve_day(organization_id=uuid4(), user_id=uuid4())
    assert day == expected
    assert zone == ("UTC" if timezone == "invalid/zone" else timezone)
