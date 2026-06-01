#!/usr/bin/env bash
# Run Alembic migrations against the Postgres service in Docker Compose.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Ensuring infrastructure services are up..."
docker compose up -d postgres redis qdrant

echo "Waiting for Postgres to become healthy..."
docker compose exec -T postgres sh -c 'until pg_isready -U alphatrade -d alphatrade; do sleep 1; done'

echo "Running Alembic migrations in backend container..."
docker compose run --rm --no-deps --entrypoint alembic backend upgrade head

echo "Migrations complete."
