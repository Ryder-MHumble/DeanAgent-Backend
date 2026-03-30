#!/usr/bin/env python3
"""Migrate legacy achievements from scholars JSON columns to relation tables.

Usage:
  ./.venv/bin/python scripts/migration/migrate_scholar_achievements.py --dry-run
  ./.venv/bin/python scripts/migration/migrate_scholar_achievements.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from typing import Any

try:
    from scripts.migration.components.runtime import (
        close_postgres_pool,
        get_postgres_pool,
        init_postgres_pool_from_settings,
    )
except ModuleNotFoundError:  # direct execution fallback
    from components.runtime import (  # type: ignore[no-redef]
        close_postgres_pool,
        get_postgres_pool,
        init_postgres_pool_from_settings,
    )

YEAR_RE = re.compile(r"(19|20)\d{2}")


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def parse_json_maybe(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (list, dict)):
        return raw
    if not isinstance(raw, str):
        return default
    token = raw.strip()
    if not token:
        return default
    value: Any = token
    for _ in range(3):
        if not isinstance(value, str):
            return value
        try:
            value = json.loads(value)
        except Exception:
            return default
    return value if value is not None else default


def split_people(raw: Any) -> list[str]:
    value = parse_json_maybe(raw, raw)
    if value is None:
        return []
    if isinstance(value, list):
        seen: set[str] = set()
        out: list[str] = []
        for item in value:
            token = clean_text(item)
            if not token:
                continue
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(token)
        return out
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        normalized = text
        for sep in ("；", ";", "，", ",", "、", "|", "/", "\n", "\r", "\t"):
            normalized = normalized.replace(sep, "|")
        return split_people([token for token in normalized.split("|") if token.strip()])
    return []


def to_year(raw: Any) -> int | None:
    text = clean_text(raw)
    if not text:
        return None
    try:
        year = int(float(text))
    except Exception:
        m = YEAR_RE.search(text)
        if not m:
            return None
        year = int(m.group(0))
    if year < 1900 or year > 2100:
        return None
    return year


def to_int(raw: Any, default: int = -1) -> int:
    try:
        return int(raw)
    except Exception:
        return default


def stable_bigint(*parts: Any) -> int:
    payload = "|".join(clean_text(p) for p in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)
    return value or 1


def normalize_publication(raw: Any, scholar_id: str, idx: int) -> dict[str, Any] | None:
    item = parse_json_maybe(raw, raw)
    if not isinstance(item, dict):
        return None
    title = clean_text(item.get("title"))
    if not title:
        return None
    venue = clean_text(item.get("venue"))
    year = to_year(item.get("year"))
    authors = split_people(item.get("authors"))
    url = clean_text(item.get("url"))
    citation_count = to_int(item.get("citation_count"), default=-1)
    is_corresponding = bool(item.get("is_corresponding", False))
    added_by = clean_text(item.get("added_by")) or "crawler"
    return {
        "id": stable_bigint("pub", scholar_id, idx, title, venue, year or "", url, ",".join(authors)),
        "scholar_id": scholar_id,
        "title": title,
        "venue": venue or None,
        "year": year,
        "authors": authors or None,
        "url": url or None,
        "citation_count": citation_count,
        "is_corresponding": is_corresponding,
        "added_by": added_by,
    }


def normalize_patent(raw: Any, scholar_id: str, idx: int) -> dict[str, Any] | None:
    item = parse_json_maybe(raw, raw)
    if not isinstance(item, dict):
        return None
    title = clean_text(item.get("title"))
    if not title:
        return None
    patent_no = clean_text(item.get("patent_no"))
    year = to_year(item.get("year"))
    inventors = split_people(item.get("inventors"))
    patent_type = clean_text(item.get("patent_type"))
    status = clean_text(item.get("status"))
    added_by = clean_text(item.get("added_by")) or "crawler"
    return {
        "id": stable_bigint("pat", scholar_id, idx, title, patent_no, year or "", ",".join(inventors)),
        "scholar_id": scholar_id,
        "title": title,
        "patent_no": patent_no or None,
        "year": year,
        "inventors": inventors or None,
        "patent_type": patent_type or None,
        "status": status or None,
        "added_by": added_by,
    }


async def connect_pool() -> None:
    await init_postgres_pool_from_settings()


async def run(apply_changes: bool) -> None:
    await connect_pool()
    pool = get_postgres_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, representative_publications, patents
            FROM scholars
            WHERE representative_publications IS NOT NULL OR patents IS NOT NULL
            """
        )

        scholars_scanned = len(rows)
        scholars_with_pub = 0
        scholars_with_pat = 0
        pub_rows_total = 0
        pat_rows_total = 0
        pub_skipped = 0
        pat_skipped = 0
        pub_written = 0
        pat_written = 0

        for rec in rows:
            scholar_id = str(rec["id"])
            raw_pubs = parse_json_maybe(rec["representative_publications"], [])
            raw_pats = parse_json_maybe(rec["patents"], [])
            if not isinstance(raw_pubs, list):
                raw_pubs = []
            if not isinstance(raw_pats, list):
                raw_pats = []

            if raw_pubs:
                scholars_with_pub += 1
            if raw_pats:
                scholars_with_pat += 1

            normalized_pubs: list[dict[str, Any]] = []
            for i, item in enumerate(raw_pubs):
                pub_rows_total += 1
                norm = normalize_publication(item, scholar_id, i)
                if norm is None:
                    pub_skipped += 1
                    continue
                normalized_pubs.append(norm)

            normalized_pats: list[dict[str, Any]] = []
            for i, item in enumerate(raw_pats):
                pat_rows_total += 1
                norm = normalize_patent(item, scholar_id, i)
                if norm is None:
                    pat_skipped += 1
                    continue
                normalized_pats.append(norm)

            if not apply_changes:
                pub_written += len(normalized_pubs)
                pat_written += len(normalized_pats)
                continue

            # Replace per scholar when source column exists (including empty list).
            if rec["representative_publications"] is not None:
                await conn.execute(
                    "DELETE FROM scholar_publications WHERE scholar_id = $1",
                    scholar_id,
                )
                if normalized_pubs:
                    await conn.executemany(
                        """
                        INSERT INTO scholar_publications
                        (id, scholar_id, title, venue, year, authors, url, citation_count, is_corresponding, added_by)
                        VALUES ($1, $2, $3, $4, $5, $6::text[], $7, $8, $9, $10)
                        """,
                        [
                            (
                                row["id"],
                                row["scholar_id"],
                                row["title"],
                                row["venue"],
                                row["year"],
                                row["authors"],
                                row["url"],
                                row["citation_count"],
                                row["is_corresponding"],
                                row["added_by"],
                            )
                            for row in normalized_pubs
                        ],
                    )
                pub_written += len(normalized_pubs)

            if rec["patents"] is not None:
                await conn.execute(
                    "DELETE FROM scholar_patents WHERE scholar_id = $1",
                    scholar_id,
                )
                if normalized_pats:
                    await conn.executemany(
                        """
                        INSERT INTO scholar_patents
                        (id, scholar_id, title, patent_no, year, inventors, patent_type, status, added_by)
                        VALUES ($1, $2, $3, $4, $5, $6::text[], $7, $8, $9)
                        """,
                        [
                            (
                                row["id"],
                                row["scholar_id"],
                                row["title"],
                                row["patent_no"],
                                row["year"],
                                row["inventors"],
                                row["patent_type"],
                                row["status"],
                                row["added_by"],
                            )
                            for row in normalized_pats
                        ],
                    )
                pat_written += len(normalized_pats)

        target_pub_count = await conn.fetchval("SELECT COUNT(*)::bigint FROM scholar_publications")
        target_pat_count = await conn.fetchval("SELECT COUNT(*)::bigint FROM scholar_patents")

    print("")
    print("===== Scholar Achievement Migration =====")
    print(f"Mode: {'APPLY' if apply_changes else 'DRY-RUN'}")
    print(f"scholars_scanned: {scholars_scanned}")
    print(f"scholars_with_publications: {scholars_with_pub}")
    print(f"scholars_with_patents: {scholars_with_pat}")
    print(f"legacy_publication_rows_total: {pub_rows_total}")
    print(f"legacy_patent_rows_total: {pat_rows_total}")
    print(f"publication_rows_skipped_invalid: {pub_skipped}")
    print(f"patent_rows_skipped_invalid: {pat_skipped}")
    print(f"publication_rows_written: {pub_written}")
    print(f"patent_rows_written: {pat_written}")
    print(f"scholar_publications_table_count: {target_pub_count}")
    print(f"scholar_patents_table_count: {target_pat_count}")

    await close_postgres_pool()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate scholar achievements to relation tables")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview only")
    mode.add_argument("--apply", action="store_true", help="Apply migration")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run(apply_changes=bool(args.apply)))


if __name__ == "__main__":
    main()
