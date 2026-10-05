"""Pytest plugin: real HTTP cannot leave the offline acceptance process.

TestClient and MockTransport remain usable. PostgreSQL uses a disposable local
database. Neither a real Telegram token nor a market provider can bypass this.
"""

import httpx
import pytest
import requests


@pytest.fixture(autouse=True)
def prohibit_real_http(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("Offline acceptance forbids real HTTP transport")

    async def async_refused(*args, **kwargs):
        refused()

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refused)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", async_refused)
    monkeypatch.setattr(requests.Session, "send", refused)
