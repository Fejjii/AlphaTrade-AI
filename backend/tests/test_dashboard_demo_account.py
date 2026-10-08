"""Demo Dashboard account reads, roles, failure and native quantity semantics."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select

from app.core.blofin_readonly_access import get_readonly_account_provider
from app.core.config import ExchangeMode
from app.db.models import BloFinDemoSyncSnapshot, JournalTrade
from app.providers.exchange.blofin_account import BloFinAccountProvider
from app.providers.exchange.blofin_client import BloFinClient
from app.providers.exchange.errors import ExchangeRequestError
from app.schemas.blofin_sync import BloFinSyncSnapshotItem
from app.services.dashboard.demo_account import project_demo_account
from tests.test_at037_tradingview_blofin import ORG_A, _login
from tests.test_at037_tradingview_blofin import client as demo_client
from tests.test_external_integrations_acceptance import readonly_settings

__all__ = ["demo_client"]


def configure(settings):
    safe = readonly_settings()
    for key in (
        "blofin_readonly_sync_enabled",
        "blofin_readonly_api_key",
        "blofin_readonly_api_secret",
        "blofin_readonly_api_passphrase",
        "blofin_demo_rest_base_url",
    ):
        setattr(settings, key, getattr(safe, key))


def transport(seen, *, positions=None, fail=False):
    def handle(request):
        seen.append((request.method, request.url.path))
        assert request.url.host == "demo-trading-openapi.blofin.com"
        if fail:
            return httpx.Response(200, json={"code": "51000", "msg": "opaque secret error"})
        data = {
            "/api/v1/user/query-apikey": {"readOnly": 1},
            "/api/v1/account/balance": {
                "details": [
                    {"currency": "USDT", "balance": "1000.25", "available": "900.125"},
                ]
            },
            "/api/v1/account/positions": positions
            if positions is not None
            else [
                {
                    "instId": "BTC-USDT",
                    "positionSide": "net",
                    "positions": "-0.1",
                    "averagePrice": "82894",
                    "markPrice": "82895",
                    "unrealizedPnl": "-0.0001",
                    "leverage": "1",
                }
            ],
        }[request.url.path]
        return httpx.Response(200, json={"code": "0", "data": data})

    return httpx.MockTransport(handle)


def wire(monkeypatch, seen, **kwargs):
    monkeypatch.setattr(
        "app.services.blofin_sync_service.get_readonly_account_provider",
        lambda settings: get_readonly_account_provider(
            settings, transport=transport(seen, **kwargs)
        ),
    )


def test_account_refresh_is_separate_from_orders_and_journal(demo_client, monkeypatch):
    client, factory, settings = demo_client
    owner = _login(client, "at037-a@test.example")
    assert client.get("/dashboard/demo-account", headers=owner).json()["status"] == "inactive"
    configure(settings)
    seen = []
    wire(monkeypatch, seen)
    empty = client.get("/dashboard/demo-account", headers=owner)
    assert empty.json()["status"] == "not_synced"
    assert empty.json()["can_refresh"] is True
    assert seen == []
    response = client.post("/dashboard/demo-account/refresh", headers=owner)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["venue"] == "BLOFIN_DEMO"
    assert data["read_only"] is True
    assert data["status"] == "ok"
    assert data["balances"] == [{"asset": "USDT", "total": "1000.25", "available": "900.125"}]
    assert data["positions"][0]["contracts"] == "0.1"
    assert data["positions"][0]["side"] == "short"
    assert data["positions"][0]["mark_price"] == "82895"
    assert data["positions"][0]["unrealized_pnl"] == "-0.0001"
    assert data["position_count"] == 1
    assert response.headers["cache-control"] == "private, no-store"
    assert "provenance" not in data and "error_summary" not in data
    assert seen == [
        ("GET", path)
        for path in (
            "/api/v1/user/query-apikey",
            "/api/v1/account/balance",
            "/api/v1/account/positions",
        )
    ]
    saved = client.get("/dashboard/demo-account", headers=owner)
    assert saved.json()["snapshot_id"] == data["snapshot_id"]
    assert saved.headers["cache-control"] == "private, no-store"
    assert len(seen) == 3  # Reading Dashboard does not call the venue.
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(JournalTrade)) == 0
        assert session.scalar(select(func.count()).select_from(BloFinDemoSyncSnapshot)) == 1


def test_roles_and_tenant_boundaries(demo_client, monkeypatch):
    client, _, settings = demo_client
    configure(settings)
    seen = []
    wire(monkeypatch, seen)
    owner = _login(client, "at037-a@test.example")
    assert client.post("/dashboard/demo-account/refresh", headers=owner).status_code == 200
    for email in ("at037-viewer@test.example", "at037-trader@test.example"):
        headers = _login(client, email)
        data = client.get("/dashboard/demo-account", headers=headers).json()
        assert data["status"] == "ok" and data["can_refresh"] is False
        assert client.post("/dashboard/demo-account/refresh", headers=headers).status_code == 403
    other = _login(client, "at037-b@test.example")
    data = client.get("/dashboard/demo-account", headers=other).json()
    assert data["status"] == "not_synced" and data["positions"] == []
    assert len(seen) == 3
    assert client.get("/dashboard/demo-account").status_code == 401


def test_dashboard_uses_existing_execution_demo_account_sync(demo_client, monkeypatch):
    client, _, settings = demo_client
    configure(settings)
    settings.blofin_readonly_sync_enabled = False
    settings.exchange_mode = ExchangeMode.PAPER_EXCHANGE_DEMO
    settings.blofin_demo_enabled = True
    settings.blofin_api_key = "fixture-key"
    settings.blofin_api_secret = "fixture-secret"
    settings.blofin_api_passphrase = "fixture-pass"
    seen = []
    monkeypatch.setattr(
        "app.services.blofin_sync_service.get_demo_account_provider",
        lambda _: get_readonly_account_provider(readonly_settings(), transport=transport(seen)),
    )
    owner = _login(client, "at037-a@test.example")
    data = client.post("/dashboard/demo-account/refresh", headers=owner).json()
    assert data["status"] == "ok" and data["position_count"] == 1
    assert len(seen) == 3


def test_failure_replaces_latest_without_old_success_fallback(demo_client, monkeypatch):
    client, _, settings = demo_client
    configure(settings)
    owner = _login(client, "at037-a@test.example")
    seen = []
    wire(monkeypatch, seen)
    assert client.post("/dashboard/demo-account/refresh", headers=owner).json()["status"] == "ok"
    wire(monkeypatch, seen, fail=True)
    failed = client.post("/dashboard/demo-account/refresh", headers=owner).json()
    assert failed["status"] == "unavailable"
    assert failed["position_count"] is None and failed["balances"] == []
    latest = client.get("/dashboard/demo-account", headers=owner).json()
    assert latest["snapshot_id"] == failed["snapshot_id"]
    assert latest["status"] == "unavailable"
    assert "opaque secret error" not in str(latest)


def test_stale_truncated_and_empty_snapshots(demo_client, monkeypatch):
    client, factory, settings = demo_client
    configure(settings)
    owner = _login(client, "at037-a@test.example")
    wire(monkeypatch, [], positions=[])
    data = client.post("/dashboard/demo-account/refresh", headers=owner).json()
    assert data["position_count"] == 0 and data["status"] == "ok"
    with factory() as session:
        row = session.scalars(select(BloFinDemoSyncSnapshot)).one()
        row.synced_at = datetime.now(UTC) - timedelta(hours=1)
        row.positions_snapshot = {"items": [], "truncated": True}
        session.commit()
    data = client.get("/dashboard/demo-account", headers=owner).json()
    assert data["status"] == "stale"
    assert data["positions_truncated"] is True and data["position_count"] is None
    settings.blofin_readonly_sync_enabled = False
    assert client.post("/dashboard/demo-account/refresh", headers=owner).status_code == 409
    assert client.get("/dashboard/demo-account", headers=owner).json()["status"] == "inactive"


@pytest.mark.parametrize(
    "data",
    [
        None,
        {},
        {"details": None},
        [None],
        [
            {"currency": "USDT", "balance": "NaN", "available": "1"},
        ],
        [{"currency": "USDT", "balance": "1"}],
    ],
)
def test_malformed_native_balances_never_become_zero(data):
    provider = native_provider(data)
    with pytest.raises(ExchangeRequestError):
        provider.get_balances()


@pytest.mark.parametrize(
    "data",
    [
        None,
        {},
        [None],
        [{"instId": "BTC-USDT"}],
        [
            {"instId": "BTC-USDT", "positions": "Infinity", "positionSide": "net"},
        ],
        [{"instId": "BTC-USDT", "positions": "1", "positionSide": "unknown"}],
    ],
)
def test_malformed_native_positions_never_become_empty(data):
    with pytest.raises(ExchangeRequestError):
        native_provider(data).get_positions()


def native_provider(data):
    client = BloFinClient(
        base_url="https://demo-trading-openapi.blofin.com",
        api_key="fixture-key",
        api_secret="fixture-secret",
        api_passphrase="fixture-pass",
        max_retries=0,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"code": "0", "data": data})
        ),
    )
    return BloFinAccountProvider(client)


def test_optional_unknown_values_remain_unknown_and_signed_size_is_preserved():
    position = native_provider(
        [
            {
                "instId": "BTC-USDT",
                "positions": "-0.1",
                "positionSide": "net",
                "upl": "0",
            }
        ]
    ).get_positions()[0]
    assert position.size == Decimal("-0.1")
    assert position.unrealized_pnl == 0
    assert position.mark_price is None and position.entry_price is None


@pytest.mark.parametrize(
    "change",
    [
        {"provider": "mock"},
        {"provenance": {"read_only": True}},
        {"account_snapshot": {"balances": [{"asset": "USDT", "total": "bad", "available": "0"}]}},
    ],
)
def test_untrusted_or_malformed_saved_evidence_is_unavailable(change):
    snapshot = BloFinSyncSnapshotItem(
        id=uuid4(),
        organization_id=ORG_A,
        synced_at=datetime.now(UTC),
        health_status="ok",
        provider="blofin_demo",
        exchange_mode="paper_internal",
        account_snapshot={"balances": []},
        positions_snapshot={"items": []},
        provenance={"read_only": True, "order_mutations": False},
    ).model_copy(update=change)
    data = project_demo_account(snapshot, settings=readonly_settings(), can_refresh=True)
    assert data.status == "unavailable" and data.position_count is None
