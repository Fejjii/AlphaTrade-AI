#!/usr/bin/env bash
# End-to-end local backup/restore drill for AT-019.
# - Uses Docker Compose Postgres only
# - Inserts a non-sensitive marker, dumps, destroys DB, restores, verifies marker
# - Writes JSON summary under .ai/local/backups/ (gitignored)
# Requires CONFIRM=yes.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "${CONFIRM:-}" != "yes" ]]; then
  echo "Refusing local restore drill without CONFIRM=yes." >&2
  echo "Example: CONFIRM=yes $0" >&2
  exit 1
fi

SERVICE="${POSTGRES_SERVICE:-postgres}"
PG_USER="${POSTGRES_USER:-alphatrade}"
PG_DB="${POSTGRES_DB:-alphatrade}"
MARKER_SCHEMA="at019_drill"
MARKER_UUID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
MARKER_LABEL="at019-local-drill"
SUMMARY_DIR="$ROOT_DIR/.ai/local/backups/postgres"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SUMMARY_FILE="$SUMMARY_DIR/drill-summary-${STAMP}.json"

mkdir -p "$SUMMARY_DIR"

echo "== AT-019 local backup/restore drill =="
echo "marker_uuid=${MARKER_UUID}"

echo "Ensuring Postgres is up..."
docker compose up -d "$SERVICE"
docker compose exec -T "$SERVICE" \
  sh -c "until pg_isready -U '$PG_USER' -d '$PG_DB'; do sleep 1; done"

# Prefer full schema via Alembic when backend image/build is available; fall back to
# marker-only schema so the drill still proves dump/restore without building the API.
if docker compose run --rm --no-deps --entrypoint alembic backend upgrade head >/tmp/at019-alembic.log 2>&1; then
  MIGRATIONS="applied"
  echo "Migrations: applied (alembic upgrade head)"
else
  MIGRATIONS="skipped"
  echo "Migrations: skipped (alembic unavailable or failed; using marker schema only)"
  echo "  (see /tmp/at019-alembic.log locally — do not commit)"
fi

echo "Creating marker table + row..."
docker compose exec -T "$SERVICE" psql -U "$PG_USER" -d "$PG_DB" -v ON_ERROR_STOP=1 <<SQL
CREATE SCHEMA IF NOT EXISTS ${MARKER_SCHEMA};
CREATE TABLE IF NOT EXISTS ${MARKER_SCHEMA}.restore_markers (
  id uuid PRIMARY KEY,
  label text NOT NULL,
  created_at_utc timestamptz NOT NULL DEFAULT now()
);
INSERT INTO ${MARKER_SCHEMA}.restore_markers (id, label)
VALUES ('${MARKER_UUID}', '${MARKER_LABEL}');
SQL

echo "Running backup..."
BACKUP_START="$(date +%s)"
BACKUP_OUT="$("$ROOT_DIR/scripts/backup-postgres-local.sh")"
BACKUP_END="$(date +%s)"
BACKUP_SECONDS=$((BACKUP_END - BACKUP_START))
echo "$BACKUP_OUT"

DUMP_REL="$(printf '%s\n' "$BACKUP_OUT" | awk -F= '/^  file=/{print $2; exit}')"
DUMP_BYTES="$(printf '%s\n' "$BACKUP_OUT" | awk -F= '/^  bytes=/{print $2; exit}')"
DUMP_SHA="$(printf '%s\n' "$BACKUP_OUT" | awk -F= '/^  sha256=/{print $2; exit}')"

if [[ -z "$DUMP_REL" || -z "$DUMP_SHA" ]]; then
  echo "FAIL: could not parse backup script output" >&2
  exit 1
fi

echo "Simulating data loss (DROP DATABASE)..."
docker compose exec -T "$SERVICE" psql -U "$PG_USER" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '${PG_DB}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${PG_DB};
CREATE DATABASE ${PG_DB} OWNER ${PG_USER};
SQL

echo "Running restore..."
RESTORE_START="$(date +%s)"
CONFIRM=yes DUMP_FILE="$DUMP_REL" "$ROOT_DIR/scripts/restore-postgres-local.sh"
RESTORE_END="$(date +%s)"
RESTORE_SECONDS=$((RESTORE_END - RESTORE_START))

echo "Verifying marker..."
FOUND="$(
  docker compose exec -T "$SERVICE" psql -U "$PG_USER" -d "$PG_DB" -At -v ON_ERROR_STOP=1 \
    -c "SELECT id::text FROM ${MARKER_SCHEMA}.restore_markers WHERE id = '${MARKER_UUID}';"
)"
FOUND="$(printf '%s' "$FOUND" | tr -d '[:space:]')"

if [[ "$FOUND" != "$MARKER_UUID" ]]; then
  echo "FAIL: marker not found after restore (got='${FOUND}')" >&2
  RESULT="failed"
  EXIT_CODE=1
else
  echo "OK: marker verified after restore"
  RESULT="passed"
  EXIT_CODE=0
fi

TOTAL_SECONDS=$((BACKUP_SECONDS + RESTORE_SECONDS))

cat >"$SUMMARY_FILE" <<JSON
{
  "task": "AT-019",
  "tier": "A-local-compose",
  "result": "${RESULT}",
  "generated_at_utc": "${STAMP}",
  "marker_uuid": "${MARKER_UUID}",
  "marker_label": "${MARKER_LABEL}",
  "migrations": "${MIGRATIONS}",
  "dump_file": "${DUMP_REL}",
  "dump_bytes": ${DUMP_BYTES:-0},
  "dump_sha256": "${DUMP_SHA}",
  "backup_seconds": ${BACKUP_SECONDS},
  "restore_seconds": ${RESTORE_SECONDS},
  "total_backup_restore_seconds": ${TOTAL_SECONDS},
  "secrets_included": false,
  "external_services_contacted": false
}
JSON

REL_SUMMARY="${SUMMARY_FILE#"$ROOT_DIR"/}"
echo "Summary written: ${REL_SUMMARY}"
echo "RESULT=${RESULT}"
exit "$EXIT_CODE"
