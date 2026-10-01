"""Execute the new revision only in disposable SQLite/PostgreSQL test databases."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.db import models  # noqa: F401
from app.db.base import Base


def test_watchlist_migration_round_trip(tmp_path, monkeypatch):
    url = f"sqlite+pysqlite:///{tmp_path / 'migration.sqlite'}"
    engine = create_engine(url)
    new = {"watcher_watchlists", "watcher_symbol_status"}
    Base.metadata.create_all(
        engine, tables=[table for name, table in Base.metadata.tables.items() if name not in new]
    )
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "src/app/db/migrations"))
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
    command.stamp(config, "a8c3e1b94d20")
    command.upgrade(config, "b6f2d9a10e73")
    assert new <= set(inspect(engine).get_table_names())
    assert {c["name"] for c in inspect(engine).get_columns("watcher_symbol_status")} == {
        "organization_id",
        "symbol",
        "configuration_revision",
        "observed_at",
        "payload",
    }
    command.downgrade(config, "a8c3e1b94d20")
    assert not new & set(inspect(engine).get_table_names())
    command.upgrade(config, "b6f2d9a10e73")
    assert new <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_postgres_isolated_migration_and_concurrent_revisions(monkeypatch):
    """CI's explicit disposable DB; each invocation owns a fresh schema."""
    import os
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4

    import pytest
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker

    from app.core.errors import ConflictError
    from app.db.models import Organization
    from app.repositories.watcher_watchlist import WatcherWatchlistRepository

    raw = os.environ.get("AT028_POSTGRES_URL")
    if not raw or make_url(raw).port == 15499:
        pytest.skip("Explicit disposable PostgreSQL test database unavailable locally")
    url = make_url(raw)
    assert url.database == "alphatrade_test", "Never migrate a shared/product database"
    schema = "watchlist_test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated_url = url.update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(isolated_url)
    try:
        Organization.__table__.create(engine)
        root = Path(__file__).resolve().parents[1]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "src/app/db/migrations"))
        monkeypatch.setenv(
            "ALEMBIC_DATABASE_URL", isolated_url.render_as_string(hide_password=False)
        )
        command.stamp(config, "a8c3e1b94d20")
        command.upgrade(config, "b6f2d9a10e73")
        factory = sessionmaker(engine, expire_on_commit=False)
        org = uuid4()
        with factory() as session:
            session.add(Organization(id=org, name="watchlist isolated migration"))
            session.commit()

        def write(symbol):
            with factory() as session:
                try:
                    result = WatcherWatchlistRepository(session).replace(
                        org, [(symbol, True)], expected_revision=0
                    )
                    session.commit()
                    return result.revision
                except ConflictError:
                    session.rollback()
                    return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(write, ["BTCUSDT", "ETHUSDT"]))
        assert outcomes.count(1) == 1 and outcomes.count("conflict") == 1
        command.downgrade(config, "a8c3e1b94d20")
        assert "watcher_watchlists" not in inspect(engine).get_table_names()
        command.upgrade(config, "b6f2d9a10e73")
        assert "watcher_symbol_status" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
