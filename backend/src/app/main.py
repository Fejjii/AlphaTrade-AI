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
    dashboard,
    execution,
    health,
    human_vs_system,
    journal,
    knowledge,
    lessons,
    manual_levels,
    market,
    market_watcher,
    organizations,
    paper_validation,
    positions,
    pretrade,
    proposals,
    providers,
    risk,
    strategy_library,
    strategy_modules,
    tools,
    usage,
)
from app.core.config import Settings, get_settings
from app.core.deployment_safety import deployment_posture
from app.core.errors import register_exception_handlers
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
    # TODO(slice-18): open real Qdrant/Redis clients when credentials are present.
    app.state.vector_store = get_process_vector_store()
    resolved = resolve_providers(settings)
    app.state.resolved_providers = resolved
    from app.security.rate_limit import get_rate_limiter

    limiter = get_rate_limiter(settings)
    rate_backend = "redis" if getattr(limiter, "using_redis", False) else "memory"
    logger.info("rate_limit_backend", backend=rate_backend)
    yield
    # TODO(slice-18): close Qdrant client gracefully when using live vector store.
    logger.info("shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()
    configure_logging(log_level=settings.log_level, json_logs=settings.log_json)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/docs",
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
        market_watcher.router,
        backtests.router,
        manual_levels.router,
        pretrade.router,
        human_vs_system.router,
        risk.router,
        proposals.router,
        approvals.router,
        execution.router,
        positions.router,
        journal.router,
        lessons.router,
        analytics.router,
        knowledge.router,
        audit.router,
        usage.router,
        billing.router,
        dashboard.router,
        tools.router,
    ):
        app.include_router(r)
    return app


app = create_app()
