"""Seed a synthetic, loopback-only experiment tenant for focused browser checks.

Uses trusted test fixtures, not native source records. Never enable a runtime.
The output contains short-lived local authentication; keep it outside the repository.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.support.experiment_fixtures import World

from app.core.config import Settings
from app.db.models import User
from app.schemas.experiments import ExperimentCreate
from app.security.tokens import create_access_token


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--local-jwt-secret", required=True)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if (
        url.get_backend_name() != "postgresql"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database != "alphatrade_test"
    ):
        parser.error("Only explicitly disposable loopback PostgreSQL alphatrade_test is allowed.")
    if not args.output.resolve().is_relative_to(Path("/tmp")):
        parser.error("Keep the short-lived synthetic authentication file under /tmp.")
    engine = create_engine(url)
    settings = Settings(
        _env_file=None, environment="local", provider_mode="mock", jwt_secret=args.local_jwt_secret
    )
    try:
        with Session(engine, expire_on_commit=False) as session:
            world = World(session)
            world.now = datetime.now(UTC) - timedelta(minutes=3)
            user = session.get(User, world.tenant.user_id)
            assert user is not None
            user.email = f"browser-{uuid4().hex}@example.com"
            user.email_verified = True
            world.tenant = replace(world.tenant, email=user.email)

            def create(name: str, mode: str):
                return world.service.create(
                    world.tenant,
                    ExperimentCreate(
                        name=name,
                        idempotency_key=name,
                        configuration=world.configuration(
                            mode=mode,
                            sample_target={
                                "kind": "setup_observation",
                                "minimum": 30,
                                "maximum": 100,
                            },
                        ),
                    ),
                )

            exploration = world.approve(
                world.transition(create("Nested exploration", "exploration"), "submit")
            )
            validation = world.transition(
                world.approve(
                    world.transition(create("Nested validation", "validation"), "submit")
                ),
                "start",
            )
            world.sample(validation, reference="synthetic-browser-setup")
            world.transition(create("Nested review", "exploration"), "submit")
            session.commit()
            token, _ = create_access_token(
                user_id=world.tenant.user_id,
                organization_id=world.tenant.organization_id,
                email=user.email,
                settings=settings,
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps({"token": token, "experiment_id": str(exploration.experiment_id)}) + "\n"
            )
            args.output.chmod(0o600)
            print("Seeded synthetic tenant; runtime inactive; private local auth file written.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
