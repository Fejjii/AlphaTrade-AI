#!/usr/bin/env bash
# Restore a logical dump into the local Docker Compose Postgres service only.
# Requires CONFIRM=yes. Refuses to run if DUMP_FILE is missing or empty.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SERVICE="${POSTGRES_SERVICE:-postgres}"
PG_USER="${POSTGRES_USER:-alphatrade}"
PG_DB="${POSTGRES_DB:-alphatrade}"
DUMP_FILE="${DUMP_FILE:-}"

if [[ "${CONFIRM:-}" != "yes" ]]; then
  echo "Refusing to restore without CONFIRM=yes." >&2
  echo "Example: CONFIRM=yes DUMP_FILE=.ai/local/backups/postgres/<file>.dump $0" >&2
  exit 1
fi

if [[ -z "$DUMP_FILE" ]]; then
  echo "FAIL: DUMP_FILE is required" >&2
  exit 1
fi

if [[ "$DUMP_FILE" != /* ]]; then
  DUMP_FILE="$ROOT_DIR/$DUMP_FILE"
fi

if [[ ! -f "$DUMP_FILE" ]]; then
  echo "FAIL: dump not found: $DUMP_FILE" >&2
  exit 1
fi

case "$DUMP_FILE" in
  *".."*)
    echo "FAIL: refusing dump path containing '..'" >&2
    exit 1
    ;;
esac

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

SHA="$(shasum -a 256 "$DUMP_FILE" | awk '{print $1}')"
BYTES="$(wc -c <"$DUMP_FILE" | tr -d ' ')"
REL_DUMP="${DUMP_FILE#"$ROOT_DIR"/}"

echo "Restoring dump into local Compose Postgres (destructive to ${PG_DB})..."
echo "  file=${REL_DUMP}"
echo "  bytes=${BYTES}"
echo "  sha256=${SHA}"

# Terminate other sessions, drop + recreate database, then pg_restore.
docker compose exec -T "$SERVICE" psql -U "$PG_USER" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '${PG_DB}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${PG_DB};
CREATE DATABASE ${PG_DB} OWNER ${PG_USER};
SQL

# pg_restore exit code 1 can mean warnings; treat only hard failures via pipe status.
set +e
docker compose exec -T "$SERVICE" \
  pg_restore -U "$PG_USER" -d "$PG_DB" --no-owner --no-acl \
  <"$DUMP_FILE"
RESTORE_RC=$?
set -e

if [[ "$RESTORE_RC" -gt 1 ]]; then
  echo "FAIL: pg_restore exit=${RESTORE_RC}" >&2
  exit "$RESTORE_RC"
fi

echo "OK: local Postgres restore complete (pg_restore exit=${RESTORE_RC})"
