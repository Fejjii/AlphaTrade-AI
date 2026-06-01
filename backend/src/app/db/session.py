"""Database engine and session management.

PostgreSQL is the production target. A synchronous engine keeps the persistence
layer simple and easy to test; FastAPI runs sync DB work in a threadpool. The
engine is created lazily from settings so importing this module has no side
effects (important for tests that use their own SQLite engine).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _connect_args(database_url: str) -> dict:
    # SQLite (tests) needs this flag when shared across threads.
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first use."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
            connect_args=_connect_args(settings.database_url),
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session and ensuring cleanup."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
