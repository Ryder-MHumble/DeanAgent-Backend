#!/usr/bin/env bash
set -euo pipefail

# Refresh Supabase export and load into local PostgreSQL.
# Requires:
#   - .env with SUPABASE_URL/SUPABASE_KEY and POSTGRES_* settings
#   - psql available in PATH

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

echo "[1/4] Exporting latest schema+data from Supabase ..."
python scripts/migration/export_supabase_to_sql.py --output-dir exports/sql

echo "[2/4] Loading dump into local PostgreSQL ..."
: "${POSTGRES_HOST:=127.0.0.1}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:=postgres}"
: "${POSTGRES_DB:=zgci_db}"
: "${POSTGRES_PASSWORD:=}"

if [ -n "${POSTGRES_PASSWORD}" ]; then
  export PGPASSWORD="${POSTGRES_PASSWORD}"
fi

psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 -f exports/sql/supabase_full_dump.sql

echo "[3/4] Ensuring projects table exists ..."
psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT '在研',
  category TEXT,
  pi_name TEXT NOT NULL,
  pi_institution TEXT,
  funder TEXT,
  funding_amount DOUBLE PRECISION,
  start_year INTEGER,
  end_year INTEGER,
  description TEXT,
  tags TEXT[] DEFAULT '{}',
  related_scholars JSONB DEFAULT '[]'::jsonb,
  cooperation_institutions TEXT[] DEFAULT '{}',
  outputs JSONB DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  custom_fields JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_category ON projects(category);
CREATE INDEX IF NOT EXISTS idx_projects_pi_name ON projects(pi_name);
CREATE INDEX IF NOT EXISTS idx_projects_updated_at ON projects(updated_at DESC);
SQL

echo "[4/4] Verifying row counts ..."
python scripts/migration/verify_local_pg_counts.py

echo "Done: local PostgreSQL has been refreshed from Supabase export."
