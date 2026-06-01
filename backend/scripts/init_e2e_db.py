"""Create SQLite schema for local Playwright E2E runs."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, event

from app.db import models as _models  # noqa: F401 — register ORM tables
from app.db.base import Base


def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "sqlite+pysqlite:///./.e2e-alphatrade.db")
    engine = create_engine(database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn: object, _record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    engine.dispose()
    print(f"E2E database ready at {database_url}")


if __name__ == "__main__":
    main()
