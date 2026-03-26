#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

if [ -f .env ]; then
  # shellcheck disable=SC1091
  source .env
fi

: "${POSTGRES_HOST:=127.0.0.1}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:=postgres}"
: "${POSTGRES_DB:=zgci_db}"
: "${POSTGRES_PASSWORD:=}"

if [ -n "${POSTGRES_PASSWORD}" ]; then
  export PGPASSWORD="${POSTGRES_PASSWORD}"
fi

run_as_postgres=false

CURRENT_DB_USER=$(
  psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -At \
    -c "SELECT current_user"
)
SCHOLARS_OWNER=$(
  psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -At \
    -c "SELECT tableowner FROM pg_tables WHERE schemaname='public' AND tablename='scholars'"
)
INSTITUTIONS_OWNER=$(
  psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -At \
    -c "SELECT tableowner FROM pg_tables WHERE schemaname='public' AND tablename='institutions'"
)

if [ "${CURRENT_DB_USER}" != "${SCHOLARS_OWNER}" ] || [ "${CURRENT_DB_USER}" != "${INSTITUTIONS_OWNER}" ]; then
  echo "Current DB user: ${CURRENT_DB_USER}"
  echo "scholars owner: ${SCHOLARS_OWNER}"
  echo "institutions owner: ${INSTITUTIONS_OWNER}"
  if command -v sudo >/dev/null 2>&1; then
    echo "Switching to postgres via sudo for index creation..."
    run_as_postgres=true
  else
    echo "ERROR: current user is not table owner and sudo is unavailable."
    echo "Please rerun with owner credentials (typically POSTGRES_USER=postgres)."
    exit 1
  fi
fi

if [ "${run_as_postgres}" = true ]; then
  sudo -u postgres psql -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 < scripts/migration/optimize_pg_performance.sql
else
  psql \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    -v ON_ERROR_STOP=1 \
    -f scripts/migration/optimize_pg_performance.sql
fi

echo "Applied PostgreSQL optimization indexes to ${POSTGRES_DB}@${POSTGRES_HOST}:${POSTGRES_PORT}"
