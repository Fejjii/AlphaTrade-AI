"""Real PostgreSQL races for signed intake and paper Candidate convergence."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import func, select

from app.core.config import Settings
from app.db.models import Organization, PaperValidationCandidate, TradingViewSignal, User
from app.repositories.tradingview_signal import TradingViewSignalRepository
from app.schemas.tradingview_signal import (
    CREATE_TRADINGVIEW_CANDIDATE_CONFIRM,
    TradingViewSignalCreateCandidateRequest,
)
from app.security.tradingview_webhook import compute_tradingview_signature
from app.services.tradingview_signal_service import TradingViewSignalService
from tests.support.postgres_persistence import phase7_plan_session_factory, requires_postgres

pytestmark = requires_postgres


def test_concurrent_signed_intake_and_candidate_creation_converge(monkeypatch) -> None:
    factory = phase7_plan_session_factory()
    organization_id, user_id = uuid4(), uuid4()
    settings = Settings(
        _env_file=None,
        environment="local",
        execution_mode="paper",
        enable_real_trading=False,
        exchange_mode="paper_internal",
        provider_mode="mock",
        rate_limit_use_redis=False,
        market_data_cache_use_redis=False,
        tradingview_webhook_enabled=True,
        tradingview_webhook_secret="postgres-tv-convergence-secret",
    )
    with factory() as session:
        session.add(Organization(id=organization_id, name="External acceptance race"))
        session.add(User(id=user_id, email="external-race@test.example", hashed_password="unused"))
        session.commit()
    body = json.dumps(
        {
            "organization_id": str(organization_id),
            "alert_id": "same-alert",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "direction": "long",
        }
    ).encode()
    stamp = int(time.time())
    signature = compute_tradingview_signature(
        body, timestamp=stamp, secret=settings.tradingview_webhook_secret
    )
    barrier = threading.Barrier(2)
    original_add = TradingViewSignalRepository.add

    def racing_add(self, row):
        barrier.wait(timeout=20)
        return original_add(self, row)

    monkeypatch.setattr(TradingViewSignalRepository, "add", racing_add)

    def ingest(_index):
        with factory() as session:
            result = TradingViewSignalService(session, settings).intake_webhook(
                body, signature_header=signature, timestamp_header=str(stamp)
            )
            session.commit()
            return result.signal.id, result.duplicate

    with ThreadPoolExecutor(max_workers=2) as pool:
        deliveries = list(pool.map(ingest, range(2)))
    assert deliveries[0][0] == deliveries[1][0]
    assert sorted(item[1] for item in deliveries) == [False, True]
    monkeypatch.setattr(TradingViewSignalRepository, "add", original_add)
    barrier = threading.Barrier(2)

    def create_candidate(_index):
        with factory() as session:
            barrier.wait(timeout=20)
            candidate = TradingViewSignalService(session, settings).create_candidate(
                deliveries[0][0],
                TradingViewSignalCreateCandidateRequest(
                    confirm=CREATE_TRADINGVIEW_CANDIDATE_CONFIRM
                ),
                organization_id=organization_id,
                user_id=user_id,
            )
            session.commit()
            return candidate.candidate_id, candidate.already_exists

    with ThreadPoolExecutor(max_workers=2) as pool:
        candidates = list(pool.map(create_candidate, range(2)))
    assert candidates[0][0] == candidates[1][0]
    assert sorted(item[1] for item in candidates) == [False, True]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(TradingViewSignal)) == 1
        assert session.scalar(select(func.count()).select_from(PaperValidationCandidate)) == 1
