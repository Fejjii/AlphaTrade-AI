"""Loopback-only synthetic screening dependency for the real local API/browser.

The application routes/auth/database are real. Public acquisition alone is replaced
with original tagged synthetic receipts. Runtime settings remain disarmed; no
production dependency or operator flag is changed. Never deploy this test harness.
"""

import os

from sqlalchemy.engine import make_url
from tests.support.trendpulse_screening import DelayedReplayAcquirer, after_close

from app.api.routes.trendpulse_screening import get_screening_service
from app.core.config import get_settings
from app.core.dependencies import SessionDep
from app.main import create_app
from app.strategy_brain.trendpulse_screening.service import TrendPulseScreeningService

settings = get_settings()
url = make_url(settings.database_url)
if not (
    settings.environment == "local"
    and settings.provider_mode == "mock"
    and not settings.worker_enabled
    and not settings.enable_real_trading
    and not settings.trendpulse_screening_enabled
    and url.host in {"127.0.0.1", "localhost"}
    and url.database == "alphatrade_test"
):
    raise RuntimeError("Research browser fixture requires disarmed disposable local/mock settings.")

app = create_app(settings)


@app.middleware("http")
async def fixture_identity(request, call_next):
    response = await call_next(request)
    response.headers["X-Synthetic-Fixture-Process"] = str(os.getpid())
    return response


def synthetic_service(session: SessionDep):
    return TrendPulseScreeningService(
        session,
        settings.model_copy(update={"trendpulse_screening_enabled": True}),
        acquirer=DelayedReplayAcquirer(),
        clock=after_close,
    )


app.dependency_overrides[get_screening_service] = synthetic_service
