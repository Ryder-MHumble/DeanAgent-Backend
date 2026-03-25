#!/usr/bin/env python3
"""Export Supabase public schema and data to SQL files.

This script uses Supabase REST + OpenAPI introspection so it can work even
without direct Postgres credentials.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


FK_RE = re.compile(r"<fk table='([^']+)' column='([^']+)'/>")


def load_dotenv(path: Path) -> None:
    """Load `.env` variables into process env (without overriding existing vars)."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def http_get_json(url: str, headers: dict[str, str], timeout: int = 60) -> tuple[Any, dict[str, str]]:
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
            response_headers = {k.lower(): v for k, v in resp.headers.items()}
            return json.loads(payload), response_headers
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}\n{body[:1000]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error for {url}: {exc}") from exc


def parse_pk_and_fk(description: str | None) -> tuple[bool, list[tuple[str, str]]]:
    if not description:
        return False, []
    is_pk = "<pk/>" in description
    fks = FK_RE.findall(description)
    return is_pk, fks


def map_sql_type(prop: dict[str, Any]) -> str:
    fmt = prop.get("format")
    typ = prop.get("type")
    max_len = prop.get("maxLength")

    if fmt == "character varying":
        return f"VARCHAR({max_len})" if max_len else "VARCHAR"
    if fmt == "text":
        return "TEXT"
    if fmt == "integer":
        return "INTEGER"
    if fmt == "smallint":
        return "SMALLINT"
    if fmt == "bigint":
        return "BIGINT"
    if fmt == "double precision":
        return "DOUBLE PRECISION"
    if fmt == "boolean":
        return "BOOLEAN"
    if fmt == "timestamp with time zone":
        return "TIMESTAMPTZ"
    if fmt == "timestamp without time zone":
        return "TIMESTAMP"
    if fmt == "date":
        return "DATE"
    if fmt == "uuid":
        return "UUID"
    if fmt == "jsonb":
        return "JSONB"
    if fmt and fmt.endswith("[]"):
        return fmt.upper()
    if typ == "array":
        items = prop.get("items", {})
        item_type = items.get("type", "string")
        if item_type == "integer":
            return "INTEGER[]"
        if item_type == "number":
            return "DOUBLE PRECISION[]"
        if item_type == "boolean":
            return "BOOLEAN[]"
        return "TEXT[]"
    if typ == "integer":
        return "INTEGER"
    if typ == "number":
        return "DOUBLE PRECISION"
    if typ == "boolean":
        return "BOOLEAN"
    return "TEXT"


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def escape_str(value: str) -> str:
    return value.replace("'", "''")


def format_default(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return f"'{escape_str(str(value))}'"

    val = value.strip()
    lowered = val.lower()
    if lowered in {"true", "false"}:
        return lowered.upper()
    # Keep function-like defaults as-is: now(), gen_random_uuid(), (gen_random_uuid())::text
    if "(" in val and ")" in val:
        return val
    if "::" in val and "'" in val:
        return val
    return f"'{escape_str(val)}'"


def sql_literal(value: Any, prop: dict[str, Any]) -> str:
    if value is None:
        return "NULL"

    fmt = prop.get("format")
    typ = prop.get("type")

    if fmt == "jsonb":
        dumped = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return f"'{escape_str(dumped)}'::jsonb"

    if (fmt and fmt.endswith("[]")) or typ == "array":
        if not isinstance(value, list):
            # Defensive fallback for unexpected payload shape
            return f"'{{{escape_str(str(value))}}}'"
        items = []
        for item in value:
            if item is None:
                items.append("NULL")
            elif isinstance(item, bool):
                items.append("TRUE" if item else "FALSE")
            elif isinstance(item, (int, float)):
                items.append(str(item))
            else:
                items.append(f"'{escape_str(str(item))}'")
        cast = map_sql_type(prop)
        return f"ARRAY[{','.join(items)}]::{cast}"

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        dumped = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return f"'{escape_str(dumped)}'::jsonb"
    return f"'{escape_str(str(value))}'"


def get_tables(openapi: dict[str, Any]) -> tuple[list[str], list[str]]:
    writable: list[str] = []
    readonly: list[str] = []
    for path, ops in openapi.get("paths", {}).items():
        if path == "/" or path.startswith("/rpc/"):
            continue
        name = path.lstrip("/")
        if "post" in ops:
            writable.append(name)
        else:
            readonly.append(name)
    return sorted(writable), sorted(readonly)


def build_schema_sql(openapi: dict[str, Any], tables: list[str]) -> tuple[str, list[dict[str, str]]]:
    defs = openapi.get("definitions", {})
    statements: list[str] = []
    fk_constraints: list[dict[str, str]] = []

    statements.append("-- Generated from Supabase OpenAPI introspection")
    statements.append("-- Note: indexes, triggers, policies, functions are not included in this export.")
    statements.append("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    statements.append("")

    for table in tables:
        if table not in defs:
            continue
        definition = defs[table]
        props = definition.get("properties", {})
        required = set(definition.get("required", []))

        col_lines: list[str] = []
        pk_columns: list[str] = []

        for col, prop in props.items():
            col_type = map_sql_type(prop)
            nullable = "" if col in required else " NULL"
            not_null = " NOT NULL" if col in required else ""
            default = format_default(prop.get("default"))
            default_sql = f" DEFAULT {default}" if default is not None else ""

            is_pk, fks = parse_pk_and_fk(prop.get("description"))
            if is_pk:
                pk_columns.append(col)
            for ref_table, ref_col in fks:
                cname = f"fk_{table}_{col}_{ref_table}_{ref_col}"
                fk_constraints.append(
                    {
                        "name": cname,
                        "table": table,
                        "column": col,
                        "ref_table": ref_table,
                        "ref_col": ref_col,
                    }
                )

            col_lines.append(
                f"  {quote_ident(col)} {col_type}{default_sql}{not_null}{nullable}"
            )

        if pk_columns:
            pk_sql = ", ".join(quote_ident(c) for c in pk_columns)
            col_lines.append(f"  PRIMARY KEY ({pk_sql})")

        create_sql = f"CREATE TABLE IF NOT EXISTS {quote_ident(table)} (\n" + ",\n".join(col_lines) + "\n);"
        statements.append(create_sql)
        statements.append("")

    for fk in fk_constraints:
        statements.append(
            "ALTER TABLE "
            f"{quote_ident(fk['table'])} "
            f"ADD CONSTRAINT {quote_ident(fk['name'])} "
            f"FOREIGN KEY ({quote_ident(fk['column'])}) "
            f"REFERENCES {quote_ident(fk['ref_table'])} ({quote_ident(fk['ref_col'])});"
        )

    statements.append("")
    return "\n".join(statements), fk_constraints


def parse_total_from_content_range(content_range: str | None) -> int | None:
    if not content_range or "/" not in content_range:
        return None
    tail = content_range.split("/", 1)[1]
    if tail == "*":
        return None
    try:
        return int(tail)
    except ValueError:
        return None


def fetch_table_rows(
    base_url: str,
    headers: dict[str, str],
    table: str,
    batch_size: int,
) -> tuple[list[dict[str, Any]], int | None]:
    rows: list[dict[str, Any]] = []
    offset = 0
    total: int | None = None

    while True:
        url = f"{base_url}/rest/v1/{quote(table)}?select=*"
        page_headers = {
            **headers,
            "Range-Unit": "items",
            "Range": f"{offset}-{offset + batch_size - 1}",
            "Prefer": "count=exact",
        }
        payload, resp_headers = http_get_json(url, page_headers)
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected payload type for table '{table}': {type(payload)}")
        if total is None:
            total = parse_total_from_content_range(resp_headers.get("content-range"))
        if not payload:
            break
        rows.extend(payload)
        offset += len(payload)
        if len(payload) < batch_size:
            break
    return rows, total


def build_data_sql(
    openapi: dict[str, Any],
    tables: list[str],
    base_url: str,
    headers: dict[str, str],
    batch_size: int,
    fk_constraints: list[dict[str, str]],
) -> tuple[str, dict[str, int]]:
    defs = openapi.get("definitions", {})
    lines: list[str] = []
    row_counts: dict[str, int] = {}

    lines.append("-- Generated data export from Supabase REST")
    lines.append("")

    ordered_tables = topological_order_tables(tables, fk_constraints)

    for table in ordered_tables:
        definition = defs.get(table)
        if not definition:
            continue
        props = definition.get("properties", {})
        columns = list(props.keys())
        col_sql = ", ".join(quote_ident(c) for c in columns)

        print(f"[data] exporting table: {table}", file=sys.stderr)
        rows, total = fetch_table_rows(base_url, headers, table, batch_size)
        row_counts[table] = len(rows)
        total_info = f"{total}" if total is not None else "unknown"
        print(
            f"[data] {table}: fetched {len(rows)} rows (reported total: {total_info})",
            file=sys.stderr,
        )

        # Self-referential hierarchy tables: insert parent rows first where possible.
        self_fk_cols = [
            fk["column"]
            for fk in fk_constraints
            if fk["table"] == table and fk["ref_table"] == table
        ]
        if rows and self_fk_cols:
            fk_col = self_fk_cols[0]
            rows.sort(
                key=lambda r: (
                    r.get(fk_col) is not None,
                    str(r.get(fk_col) or ""),
                    str(r.get("id") or ""),
                )
            )

        if not rows:
            lines.append(f"-- {table}: 0 rows")
            lines.append("")
            continue

        chunk_size = 250
        lines.append(f"-- {table}: {len(rows)} rows")
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]
            values_sql: list[str] = []
            for row in chunk:
                vals = [sql_literal(row.get(col), props[col]) for col in columns]
                values_sql.append("(" + ", ".join(vals) + ")")
            lines.append(
                f"INSERT INTO {quote_ident(table)} ({col_sql}) VALUES\n"
                + ",\n".join(values_sql)
                + ";"
            )
        lines.append("")

    return "\n".join(lines), row_counts


def build_relations_md(fk_constraints: list[dict[str, str]], readonly_views: list[str]) -> str:
    lines: list[str] = []
    lines.append("# Database Relations")
    lines.append("")
    lines.append("## Foreign Keys")
    lines.append("")
    if not fk_constraints:
        lines.append("- No foreign keys detected from OpenAPI descriptions.")
    else:
        for fk in fk_constraints:
            lines.append(
                f"- `{fk['table']}.{fk['column']}` -> `{fk['ref_table']}.{fk['ref_col']}`"
            )
    lines.append("")
    lines.append("## Read-only Views")
    lines.append("")
    if not readonly_views:
        lines.append("- None")
    else:
        for view in readonly_views:
            lines.append(f"- `{view}`")
    lines.append("")
    return "\n".join(lines)


def topological_order_tables(tables: list[str], fk_constraints: list[dict[str, str]]) -> list[str]:
    table_set = set(tables)
    deps: dict[str, set[str]] = {t: set() for t in tables}
    children: dict[str, set[str]] = {t: set() for t in tables}

    for fk in fk_constraints:
        table = fk["table"]
        ref_table = fk["ref_table"]
        if table not in table_set or ref_table not in table_set or table == ref_table:
            continue
        deps[table].add(ref_table)
        children[ref_table].add(table)

    ready = sorted([t for t, d in deps.items() if not d])
    ordered: list[str] = []

    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for child in sorted(children[current]):
            deps[child].discard(current)
            if not deps[child] and child not in ordered and child not in ready:
                ready.append(child)
        ready.sort()

    # If cyclic/unresolved, append remaining deterministically.
    remaining = [t for t in tables if t not in ordered]
    ordered.extend(sorted(remaining))
    return ordered


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Supabase schema and data to SQL files")
    parser.add_argument(
        "--output-dir",
        default="exports/sql",
        help="Output directory for generated files (default: exports/sql)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size per REST page when exporting data (default: 1000)",
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Only export schema and relation docs (skip data export)",
    )
    args = parser.parse_args()

    load_dotenv(Path(".env"))

    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    service_key = os.getenv("SUPABASE_KEY", "")

    if not base_url or not service_key:
        print("Missing SUPABASE_URL or SUPABASE_KEY in environment/.env", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Accept": "application/json",
    }

    openapi_url = f"{base_url}/rest/v1/"
    openapi_headers = {**headers, "Accept": "application/openapi+json"}
    openapi, _ = http_get_json(openapi_url, openapi_headers)

    openapi_file = output_dir / "supabase_openapi.json"
    openapi_file.write_text(
        json.dumps(openapi, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    tables, readonly_views = get_tables(openapi)
    schema_sql, fk_constraints = build_schema_sql(openapi, tables)
    relations_md = build_relations_md(fk_constraints, readonly_views)

    schema_file = output_dir / "supabase_schema.sql"
    relations_file = output_dir / "schema_relations.md"
    schema_file.write_text(schema_sql, encoding="utf-8")
    relations_file.write_text(relations_md, encoding="utf-8")

    row_counts: dict[str, int] = {}
    if not args.schema_only:
        data_sql, row_counts = build_data_sql(
            openapi=openapi,
            tables=tables,
            base_url=base_url,
            headers=headers,
            batch_size=args.batch_size,
            fk_constraints=fk_constraints,
        )
        data_file = output_dir / "supabase_data.sql"
        full_dump_file = output_dir / "supabase_full_dump.sql"
        data_file.write_text(data_sql, encoding="utf-8")
        full_dump_file.write_text(schema_sql + "\n\n" + data_sql, encoding="utf-8")

    summary = {
        "tables": tables,
        "readonly_views": readonly_views,
        "foreign_keys": fk_constraints,
        "row_counts": row_counts,
    }
    (output_dir / "export_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"OpenAPI saved: {openapi_file}")
    print(f"Schema SQL:    {schema_file}")
    print(f"Relations MD:  {relations_file}")
    if not args.schema_only:
        print(f"Data SQL:      {output_dir / 'supabase_data.sql'}")
        print(f"Full dump SQL: {output_dir / 'supabase_full_dump.sql'}")
    print(f"Summary:       {output_dir / 'export_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
