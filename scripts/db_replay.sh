#!/usr/bin/env bash
# Replay all migrations + seeds into a fresh database and run SQL assertions (supabase/tests/*.sql).
# Works against plain Postgres (CI service container) or the local Supabase DB.
#   scripts/db_replay.sh postgresql://postgres:postgres@127.0.0.1:54322/postgres
set -euo pipefail
ADMIN_URL="${1:-${DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}}"
DB="sr_replay_$$"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PSQL=(psql -v ON_ERROR_STOP=1 -q -X)
base="${ADMIN_URL%/*}"
cleanup() { "${PSQL[@]}" "$ADMIN_URL" -c "drop database if exists $DB" >/dev/null 2>&1 || true; }
trap cleanup EXIT
"${PSQL[@]}" "$ADMIN_URL" -c "create database $DB" >/dev/null
URL="$base/$DB"
for f in "$ROOT"/supabase/migrations/*.sql; do echo "migrate  $(basename "$f")"; "${PSQL[@]}" "$URL" -f "$f"; done
for f in "$ROOT"/supabase/seed/*.sql; do echo "seed     $(basename "$f")"; "${PSQL[@]}" "$URL" -f "$f"; done
for f in "$ROOT"/supabase/tests/*.sql; do echo "assert   $(basename "$f")"; "${PSQL[@]}" "$URL" -f "$f"; done
echo "db replay OK"
