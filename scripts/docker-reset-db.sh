#!/usr/bin/env bash
# Destroy local Docker volumes and recreate the database from migrations.
# Requires explicit confirmation — never drops data silently.
set -euo pipefail

if [[ "${CONFIRM:-}" != "yes" ]]; then
  echo "Refusing to reset the local Docker database without CONFIRM=yes."
  echo "This removes postgres_data and qdrant_data volumes."
  echo "Example: CONFIRM=yes ./scripts/docker-reset-db.sh"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Stopping stack and removing named volumes..."
docker compose down -v

echo "Starting infrastructure services..."
docker compose up -d postgres redis qdrant

echo "Waiting for Postgres to become healthy..."
docker compose exec -T postgres sh -c 'until pg_isready -U alphatrade -d alphatrade; do sleep 1; done'

echo "Applying migrations..."
docker compose run --rm --no-deps --entrypoint alembic backend upgrade head

echo "Local database reset complete. Start the full stack with: docker compose up --build"
