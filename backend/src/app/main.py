"""FastAPI application factory and lifecycle wiring.

Composition root: configures logging, builds the provider registry, installs
middleware and exception handlers, and mounts routers. Kept free of business
logic so it stays a thin, testable composition layer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import (
    alerts,
    analytics,
    approvals,
    audit,
    auth,
    backtests,
    billing,
    chat,
    coaching,
    dashboard,
    demo,
    exchange,
    execution,
    health,
    human_vs_system,
    journal,
    knowledge,
    learning_analytics,
    lessons,
    manual_levels,
    market,
    market_watcher,
    notifications,
    organizations,
    paper_validation,
    performance,
    positions,
    pretrade,
    proposals,
    providers,
    risk,
    strategy_library,
    strategy_modules,
    strategy_quality,
    tools,
    usage,
    validation_priority,
    worker,
)
from app.core.config import Environment, Settings, get_settings
from app.core.deployment_safety import deployment_posture
from app.core.errors import register_exception_handlers
from app.core.exchange_readiness import run_exchange_demo_startup_check
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.providers.factory import resolve_providers
from app.providers.qdrant import get_process_vector_store
from app.providers.registry import build_default_registry, get_provider_registry
from app.strategies.registry import build_default_registry as build_strategy_registry
from app.strategies.registry import get_strategy_registry
from app.tools.registry import build_default_registry as build_tool_registry
from app.tools.registry import get_tool_registry

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info(
        "startup",
        app=settings.app_name,
        version=__version__,
        **deployment_posture(settings),
    )
    run_exchange_demo_startup_check(settings, app.state.provider_registry)
    # TODO(slice-18): open real Qdrant/Redis clients when credentials are present.
    app.state.vector_store = get_process_vector_store()
    resolved = resolve_providers(settings)
    app.state.resolved_providers = resolved
    from app.security.rate_limit import get_rate_limiter

    limiter = get_rate_limiter(settings)
    rate_backend = "redis" if getattr(limiter, "using_redis", False) else "memory"
    logger.info("rate_limit_backend", backend=rate_backend)

    worker_driver = _maybe_start_in_process_worker(settings)
    app.state.worker_driver = worker_driver

    yield

    if worker_driver is not None:
        worker_driver.stop()
    # TODO(slice-18): close Qdrant client gracefully when using live vector store.
    logger.info("shutdown")


def _maybe_start_in_process_worker(settings: Settings):
    """Start the background worker on a daemon thread when so configured.

    Only runs when ``WORKER_ENABLED=true`` and ``WORKER_MODE=in_process``; the
    recommended deployment uses a dedicated worker process instead.
    """
    if not (settings.worker_enabled and settings.worker_mode == "in_process"):
        return None
    from app.workers.entrypoint import build_driver

    driver = build_driver(settings)
    driver.start_background_thread()
    logger.info("worker_in_process_enabled", worker_name=settings.worker_name)
    return driver


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()
    configure_logging(log_level=settings.log_level, json_logs=settings.log_json)

    docs_enabled = settings.environment == Environment.LOCAL
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.provider_registry = build_default_registry(settings)
    app.state.strategy_registry = build_strategy_registry()
    app.state.tool_registry = build_tool_registry(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        RequestContextMiddleware,
        request_id_header=settings.request_id_header,
        trace_id_header=settings.trace_id_header,
    )

    register_exception_handlers(app)

    # Resolve shared resources from app.state so the same registry instance is
    # used across requests and can be overridden in tests.
    app.dependency_overrides[get_settings] = lambda: app.state.settings
    app.dependency_overrides[get_provider_registry] = lambda: app.state.provider_registry
    app.dependency_overrides[get_strategy_registry] = lambda: app.state.strategy_registry
    app.dependency_overrides[get_tool_registry] = lambda: app.state.tool_registry

    for r in (
        health.router,
        providers.router,
        auth.router,
        organizations.router,
        chat.router,
        market.router,
        strategy_modules.router,
        strategy_library.router,
        paper_validation.router,
        alerts.router,
        notifications.router,
        market_watcher.router,
        backtests.router,
        manual_levels.router,
        pretrade.router,
        human_vs_system.router,
        risk.router,
        proposals.router,
        approvals.router,
        execution.router,
        exchange.router,
        positions.router,
        journal.router,
        lessons.router,
        analytics.router,
        learning_analytics.router,
        validation_priority.router,
        strategy_quality.router,
        coaching.router,
        performance.router,
        knowledge.router,
        audit.router,
        usage.router,
        billing.router,
        dashboard.router,
        demo.router,
        tools.router,
        worker.router,
    ):
        app.include_router(r)
    return app


app = create_app()
