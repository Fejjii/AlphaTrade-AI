#!/usr/bin/env bash
# Logical backup of the local Docker Compose Postgres service only.
# Never accepts DATABASE_URL / remote hosts. Dumps land under .ai/local/ (gitignored).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-alphatrade}"
SERVICE="${POSTGRES_SERVICE:-postgres}"
PG_USER="${POSTGRES_USER:-alphatrade}"
PG_DB="${POSTGRES_DB:-alphatrade}"
OUT_DIR="${BACKUP_OUT_DIR:-$ROOT_DIR/.ai/local/backups/postgres}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="${OUT_DIR}/alphatrade-local-${STAMP}.dump"

if ! command -v docker >/dev/null 2>&1; then
  echo "FAIL: docker not found" >&2
  exit 1
fi

if ! docker compose ps --status running --services 2>/dev/null | grep -qx "$SERVICE"; then
  echo "Starting local Compose Postgres ($SERVICE)..."
  docker compose up -d "$SERVICE"
fi

echo "Waiting for Postgres health..."
docker compose exec -T "$SERVICE" \
  sh -c "until pg_isready -U '$PG_USER' -d '$PG_DB'; do sleep 1; done"

mkdir -p "$OUT_DIR"

echo "Dumping database via docker compose exec (custom format)..."
docker compose exec -T "$SERVICE" \
  pg_dump -U "$PG_USER" -d "$PG_DB" -Fc --no-owner --no-acl \
  >"$OUT_FILE"

if [[ ! -s "$OUT_FILE" ]]; then
  echo "FAIL: dump file empty: $OUT_FILE" >&2
  rm -f "$OUT_FILE"
  exit 1
fi

BYTES="$(wc -c <"$OUT_FILE" | tr -d ' ')"
SHA="$(shasum -a 256 "$OUT_FILE" | awk '{print $1}')"

# Path relative to repo for safer logging (no secrets)
REL_OUT="${OUT_FILE#"$ROOT_DIR"/}"

cat <<EOF
OK: local Postgres backup complete
  project=${COMPOSE_PROJECT}
  service=${SERVICE}
  database=${PG_DB}
  file=${REL_OUT}
  bytes=${BYTES}
  sha256=${SHA}
EOF
