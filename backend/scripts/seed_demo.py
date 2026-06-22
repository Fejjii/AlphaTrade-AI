"""Seed synthetic paper-only demo tenant data (local/staging CLI).

Usage:
  cd backend
  DEMO_SEED_PASSWORD='your-staging-password' uv run python scripts/seed_demo.py

Local default password (documented in docs/demo_script.md only):
  DemoPaper2026!  — used when DEMO_SEED_PASSWORD is unset and ENVIRONMENT=local.

Never run in production. Passwords are never logged.
"""

from __future__ import annotations

import os
import sys

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.demo_seed_service import DemoSeedService, assert_demo_seed_allowed


def main() -> int:
    settings = get_settings()
    try:
        assert_demo_seed_allowed(settings)
    except Exception as exc:
        print(f"Demo seed refused: {exc}", file=sys.stderr)
        return 1

    password = os.environ.get("DEMO_SEED_PASSWORD")
    factory = get_session_factory()
    with factory() as session:
        service = DemoSeedService(session, settings)
        result = service.seed(password=password)
        print(
            "Demo seed OK — "
            f"email={result.email} "
            f"strategies={result.strategies_seeded} "
            f"runs={result.paper_runs_seeded} "
            f"alerts={result.alerts_seeded} "
            f"lessons={result.lessons_seeded} "
            f"journals={result.journals_seeded} "
            "(paper only, synthetic)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
