#!/usr/bin/env python3
"""Verify local PostgreSQL row counts against exports/sql/export_summary.json."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import asyncpg


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if v and v[0] == v[-1] and v[0] in {"'", '"'}:
            v = v[1:-1]
        os.environ.setdefault(k, v)


def get_pg_config() -> dict[str, object]:
    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")
    database = os.getenv("POSTGRES_DB", "zgci_db")
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }


async def main() -> int:
    load_dotenv(Path(".env"))

    summary_path = Path("exports/sql/export_summary.json")
    if not summary_path.exists():
        print("Missing exports/sql/export_summary.json", file=sys.stderr)
        return 1

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    expected_counts: dict[str, int] = summary.get("row_counts", {})
    tables: list[str] = summary.get("tables", [])

    if not expected_counts:
        print("No row_counts found in export_summary.json", file=sys.stderr)
        return 1

    conn = await asyncpg.connect(**get_pg_config())
    try:
        mismatches: list[str] = []
        checked = 0
        for table in tables:
            if table not in expected_counts:
                continue
            sql = f'SELECT COUNT(*)::bigint AS n FROM "{table}"'
            row = await conn.fetchrow(sql)
            got = int(row["n"]) if row else 0
            exp = int(expected_counts[table])
            checked += 1
            status = "OK" if got == exp else "DIFF"
            print(f"{table}: expected={exp} got={got} {status}")
            if got != exp:
                mismatches.append(table)

        print(f"checked_tables={checked}")
        if mismatches:
            print("mismatched_tables=" + ",".join(mismatches), file=sys.stderr)
            return 1

        print("ALL_OK=True")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(__import__("asyncio").run(main()))
