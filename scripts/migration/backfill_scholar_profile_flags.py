#!/usr/bin/env python3
"""Backfill rule-based Chinese/student profile flags into scholars.custom_fields."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import asyncpg

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.scholar.profile_classifier import classify_scholar_profile  # noqa: E402

DEFAULT_DSN = "postgresql://zgci_app:StrongPassword_ChangeMe_2026@127.0.0.1:5432/zgci_db"


def _parse_custom_fields(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _counter_key(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "unknown"


async def backfill(dsn: str, *, dry_run: bool = False) -> dict[str, Any]:
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT
              id, name, name_en, university, department, position, bio,
              custom_fields
            FROM scholars
            ORDER BY id
            """,
        )

        stats: Counter[str] = Counter()
        updates: list[tuple[str, str]] = []
        for record in rows:
            row = dict(record)
            row["custom_fields"] = _parse_custom_fields(row.get("custom_fields"))
            classified = classify_scholar_profile(row)
            flags = classified["profile_flags"]
            stats[f"chinese_{_counter_key(flags.get('is_chinese'))}"] += 1
            stats[f"student_{_counter_key(flags.get('is_current_student'))}"] += 1
            updates.append((json.dumps(classified["custom_fields"], ensure_ascii=False), row["id"]))

        if not dry_run and updates:
            await conn.executemany(
                "UPDATE scholars SET custom_fields = $1::jsonb, updated_at = NOW() WHERE id = $2",
                updates,
            )

        return {"total": len(rows), **dict(sorted(stats.items()))}
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(backfill(args.dsn, dry_run=args.dry_run))
    mode = "DRY RUN" if args.dry_run else "UPDATED"
    print(f"{mode}: {json.dumps(result, ensure_ascii=False, sort_keys=True)}")


if __name__ == "__main__":
    main()
