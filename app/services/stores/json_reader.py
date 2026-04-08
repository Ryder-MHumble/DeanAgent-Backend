"""Read and aggregate crawled article data from database only."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except (ValueError, TypeError):
        return None


def _get_client():
    from app.db.client import get_client  # noqa: PLC0415
    return get_client()


async def _fetch_db_rows_paged(
    query_builder,
    *,
    page_size: int = 1000,
    max_pages: int = 1000,
) -> list[dict[str, Any]]:
    """Execute a DB select query in pages to avoid Supabase default row caps."""
    rows: list[dict[str, Any]] = []
    start = 0

    for _ in range(max_pages):
        query = query_builder().range(start, start + page_size - 1)
        res = await query.execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    else:
        logger.warning(
            "Paged DB query reached max_pages=%d (page_size=%d), partial rows=%d",
            max_pages,
            page_size,
            len(rows),
        )

    return rows


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def get_articles(
    dimension: str,
    group: str | None = None,
    source_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict[str, Any]]:
    """Fetch articles for a dimension from database."""
    client = _get_client()

    def _build_query():
        query = client.table("articles").select("*").eq("dimension", dimension).order(
            "published_at", desc=True
        )
        if group is not None:
            query = query.eq("group_name", group)
        if source_id is not None:
            query = query.eq("source_id", source_id)
        if date_from is not None:
            query = query.gte("published_at", datetime(
                date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc
            ).isoformat())
        if date_to is not None:
            query = query.lte("published_at", datetime(
                date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc
            ).isoformat())
        return query

    rows = await _fetch_db_rows_paged(_build_query)

    # Rename group_name → group for callers
    for r in rows:
        if "group_name" in r:
            r["group"] = r.pop("group_name")
    return rows


async def get_dimension_stats() -> dict[str, dict[str, Any]]:
    """Get statistics for all dimensions from database."""
    client = _get_client()

    # Fetch in pages to avoid row caps on large datasets.
    def _build_query():
        return client.table("articles").select("dimension, source_id, crawled_at")

    rows = await _fetch_db_rows_paged(_build_query)

    stats: dict[str, dict[str, Any]] = {}
    for row in rows:
        dim = row["dimension"]
        if dim not in stats:
            stats[dim] = {
                "dimension": dim,
                "total_items": 0,
                "source_count": 0,
                "_sources": set(),
                "latest_crawl": None,
            }
        stats[dim]["total_items"] += 1
        stats[dim]["_sources"].add(row["source_id"])
        crawled = row.get("crawled_at") or ""
        if crawled and (not stats[dim]["latest_crawl"] or crawled > stats[dim]["latest_crawl"]):
            stats[dim]["latest_crawl"] = crawled

    for _, s in stats.items():
        s["source_count"] = len(s.pop("_sources"))
        s["sources"] = []
    return stats


async def get_all_articles(
    dimension: str | None = None,
    source_id: str | None = None,
    keyword: str | None = None,
    tags: list[str] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict[str, Any]]:
    """Fetch articles from all (or a specific) dimensions with filtering."""
    client = _get_client()

    def _build_query():
        query = client.table("articles").select("*").order("published_at", desc=True)

        if dimension is not None:
            query = query.eq("dimension", dimension)
        if source_id is not None:
            query = query.eq("source_id", source_id)
        if date_from is not None:
            query = query.gte("published_at", datetime(
                date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc
            ).isoformat())
        if date_to is not None:
            query = query.lte("published_at", datetime(
                date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc
            ).isoformat())
        if keyword is not None:
            query = query.or_(f"title.ilike.%{keyword}%,content.ilike.%{keyword}%")
        if tags:
            query = query.contains("tags", tags)
        return query

    rows = await _fetch_db_rows_paged(_build_query)

    for r in rows:
        if "group_name" in r:
            r["group"] = r.pop("group_name")
    return rows


async def get_all_articles_paginated(
    *,
    dimension: str | None = None,
    source_ids: list[str] | None = None,
    keyword: str | None = None,
    tags: list[str] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str = "crawled_at",
    order: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch one page of articles from DB with total count."""
    if source_ids is not None and len(source_ids) == 0:
        return [], 0

    client = _get_client()
    safe_limit = max(1, int(limit))
    safe_offset = max(0, int(offset))
    allowed_sort_fields = {"published_at", "crawled_at", "title", "importance"}
    sort_field = sort_by if sort_by in allowed_sort_fields else "crawled_at"
    is_desc = order != "asc"

    query = client.table("articles").select("*", count="exact").order(sort_field, desc=is_desc)
    if dimension is not None:
        query = query.eq("dimension", dimension)
    if source_ids is not None:
        query = query.in_("source_id", source_ids)
    if date_from is not None:
        query = query.gte(
            "published_at",
            datetime(
                date_from.year,
                date_from.month,
                date_from.day,
                tzinfo=timezone.utc,
            ).isoformat(),
        )
    if date_to is not None:
        query = query.lte(
            "published_at",
            datetime(
                date_to.year,
                date_to.month,
                date_to.day,
                23,
                59,
                59,
                tzinfo=timezone.utc,
            ).isoformat(),
        )
    if keyword is not None:
        query = query.or_(f"title.ilike.%{keyword}%,content.ilike.%{keyword}%")
    if tags:
        query = query.contains("tags", tags)

    res = await query.range(safe_offset, safe_offset + safe_limit - 1).execute()
    rows = res.data or []
    for r in rows:
        if "group_name" in r:
            r["group"] = r.pop("group_name")

    total = res.count
    if total is None:
        # Fallback when count is unavailable in DB response.
        total = safe_offset + len(rows)
        if len(rows) == safe_limit:
            total += 1
    return rows, int(total)


async def get_available_dates(dimension: str) -> list[str]:
    """Get all distinct crawl dates for a dimension, sorted desc."""
    client = _get_client()

    def _build_query():
        return client.table("articles").select("crawled_at").eq("dimension", dimension)

    rows = await _fetch_db_rows_paged(_build_query)
    dates: set[str] = set()
    for row in rows:
        d = _parse_date(row.get("crawled_at"))
        if d:
            dates.add(d.isoformat())
    return sorted(dates, reverse=True)
