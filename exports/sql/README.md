# SQL Export Bundle

This folder stores a reproducible export bundle from Supabase and is used to seed local PostgreSQL.

## Files

- `supabase_openapi.json`: Raw OpenAPI metadata from Supabase REST.
- `supabase_schema.sql`: Table DDL generated from OpenAPI.
- `supabase_data.sql`: Data INSERT statements.
- `supabase_full_dump.sql`: `schema + data` combined dump.
- `export_summary.json`: Tables, FKs, views, row counts summary.
- `schema_relations.md`: Human-readable FK and view relations.

## Refresh Export

```bash
python scripts/migration/export_supabase_to_sql.py --output-dir exports/sql
```

## Load Into Local PostgreSQL

```bash
# uses POSTGRES_* from .env
bash scripts/migration/refresh_and_load_local.sh
```

## Verify Local Row Counts

```bash
python scripts/migration/verify_local_pg_counts.py
```
