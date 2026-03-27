#!/usr/bin/env python3
"""Tag scholars from 学院导师信息.csv as 教育培养-学院学生高校导师.

Usage:
  ./.venv/bin/python scripts/migration/tag_scholars_from_academy_mentors_csv.py --dry-run
  ./.venv/bin/python scripts/migration/tag_scholars_from_academy_mentors_csv.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import settings
from app.db.pool import close_pool, get_pool, init_pool
from app.services.stores import scholar_annotation_store as annotation_store

CSV_PATH = Path("data/scholars/学院导师信息.csv")

TARGET_PROJECT_TAG: dict[str, str] = {
    "category": "教育培养",
    "subcategory": "学院学生高校导师",
    "project_id": "",
    "project_title": "",
}
SYSTEM_UPDATED_BY = "system:academy_mentor_csv"


def clean(value: Any) -> str:
    return str(value or "").strip()


def n(value: Any) -> str:
    return "".join(clean(value).replace("\u3000", " ").split()).lower()


@dataclass
class MentorRow:
    name: str
    university: str
    email: str


def load_rows() -> list[MentorRow]:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [
            MentorRow(
                name=clean(r.get("导师姓名")),
                university=clean(r.get("所属高校")),
                email=clean(r.get("邮箱")),
            )
            for r in reader
        ]
    dedup: dict[tuple[str, str, str], MentorRow] = {}
    for row in rows:
        key = (n(row.name), n(row.university), n(row.email))
        if not key[0]:
            continue
        dedup[key] = row
    return list(dedup.values())


async def connect_pool() -> None:
    if settings.POSTGRES_DSN:
        await init_pool(dsn=settings.POSTGRES_DSN)
    else:
        await init_pool(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
        )


def _choose_candidates(
    row: MentorRow,
    *,
    by_name_uni: dict[tuple[str, str], list[dict[str, Any]]],
    by_email: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    candidates = by_name_uni.get((n(row.name), n(row.university)), [])
    if not candidates and row.email:
        candidates = by_email.get(n(row.email), [])
    if not candidates:
        return []

    if row.email:
        exact_email = [c for c in candidates if n(c.get("email")) == n(row.email)]
        if exact_email:
            return exact_email

    # If email is absent or no exact-email hit, keep all same-name candidates in parent university.
    return candidates


async def run(apply_changes: bool) -> None:
    rows = load_rows()
    await connect_pool()
    pool = get_pool()

    async with pool.acquire() as conn:
        scholars = [
            dict(r)
            for r in await conn.fetch(
                """
                SELECT id, name, university, email, updated_at
                FROM scholars
                """
            )
        ]
        scholar_cols = {
            str(r["column_name"])
            for r in await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='scholars'
                """
            )
        }

        by_name_uni: dict[tuple[str, str], list[dict[str, Any]]] = {}
        by_email: dict[str, list[dict[str, Any]]] = {}
        for s in scholars:
            by_name_uni.setdefault((n(s.get("name")), n(s.get("university"))), []).append(s)
            email_key = n(s.get("email"))
            if email_key:
                by_email.setdefault(email_key, []).append(s)

        matched_ids: set[str] = set()
        unresolved_rows: list[MentorRow] = []
        ambiguous_rows = 0

        for row in rows:
            candidates = _choose_candidates(
                row,
                by_name_uni=by_name_uni,
                by_email=by_email,
            )
            if not candidates:
                unresolved_rows.append(row)
                continue
            if len(candidates) > 1:
                ambiguous_rows += 1
            for c in candidates:
                matched_ids.add(clean(c.get("id")))

        update_payload: dict[str, Any] = {}
        if "project_tags" in scholar_cols:
            update_payload["project_tags"] = [TARGET_PROJECT_TAG]
        if "project_category" in scholar_cols:
            update_payload["project_category"] = TARGET_PROJECT_TAG["category"]
        if "project_subcategory" in scholar_cols:
            update_payload["project_subcategory"] = TARGET_PROJECT_TAG["subcategory"]
        if "is_cobuild_scholar" in scholar_cols:
            update_payload["is_cobuild_scholar"] = True
        if "relation_updated_by" in scholar_cols:
            update_payload["relation_updated_by"] = SYSTEM_UPDATED_BY
        if "relation_updated_at" in scholar_cols:
            update_payload["relation_updated_at"] = "now()"
        if "updated_at" in scholar_cols:
            update_payload["updated_at"] = "now()"

        rows_updated = 0
        if apply_changes and matched_ids:
            for scholar_id in sorted(matched_ids):
                if update_payload:
                    set_parts: list[str] = []
                    params: list[Any] = []
                    idx = 1
                    for key, value in update_payload.items():
                        if value == "now()":
                            set_parts.append(f"{key} = now()")
                            continue
                        params.append(value)
                        set_parts.append(f"{key} = ${idx}")
                        idx += 1
                    params.append(scholar_id)
                    await conn.execute(
                        f"UPDATE scholars SET {', '.join(set_parts)} WHERE id = ${idx}",
                        *params,
                    )
                annotation_store.update_relation(
                    scholar_id,
                    {
                        "project_tags": [TARGET_PROJECT_TAG],
                        "is_cobuild_scholar": True,
                        "relation_updated_by": SYSTEM_UPDATED_BY,
                    },
                )
                rows_updated += 1

    print("")
    print("===== Academy Mentor Tag Sync =====")
    print(f"Mode: {'APPLY' if apply_changes else 'DRY-RUN'}")
    print(f"csv_unique_rows: {len(rows)}")
    print(f"matched_scholars: {len(matched_ids)}")
    print(f"ambiguous_source_rows: {ambiguous_rows}")
    print(f"unresolved_rows: {len(unresolved_rows)}")
    print(f"rows_updated: {rows_updated}")
    if unresolved_rows:
        print("unresolved_samples:")
        for row in unresolved_rows[:20]:
            print(f"  - {row.name} | {row.university} | {row.email or '(empty)'}")

    await close_pool()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tag scholars from 学院导师信息.csv with 教育培养-学院学生高校导师",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview only")
    mode.add_argument("--apply", action="store_true", help="Apply updates")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run(apply_changes=bool(args.apply)))


if __name__ == "__main__":
    main()
