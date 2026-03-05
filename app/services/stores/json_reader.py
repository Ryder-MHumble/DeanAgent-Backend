"""Read and aggregate crawled JSON data from data/raw/ directory."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from app.crawlers.utils.json_storage import DATA_DIR as RAW_DATA_DIR
from app.crawlers.utils.json_storage import LATEST_FILENAME

logger = logging.getLogger(__name__)


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except (ValueError, TypeError):
        return None


def get_articles(
    dimension: str,
    group: str | None = None,
    source_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict[str, Any]]:
    """Read articles from data/raw/{dimension}/ latest.json files.

    Supports filtering by group, source_id, and date range (via published_at).
    Returns a flat list of article dicts sorted by published_at desc.
    """
    dim_dir = RAW_DATA_DIR / dimension
    if not dim_dir.exists():
        logger.warning("Dimension directory not found: %s", dim_dir)
        return []

    all_items: list[dict[str, Any]] = []
    json_files = list(dim_dir.rglob(LATEST_FILENAME))

    for json_file in json_files:
        rel = json_file.relative_to(dim_dir)
        parts = rel.parts

        if len(parts) == 3:
            file_group, file_source, _ = parts
        elif len(parts) == 2:
            file_group = None
            file_source, _ = parts
        else:
            continue

        if group and file_group != group:
            continue
        if source_id and file_source != source_id:
            continue

        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read %s: %s", json_file, e)
            continue

        source_meta = {
            "source_id": data.get("source_id", file_source),
            "source_name": data.get("source_name", file_source),
            "dimension": data.get("dimension", dimension),
            "group": data.get("group", file_group),
            "crawled_at": data.get("crawled_at"),
        }

        for item in data.get("items", []):
            pub_date = _parse_date(item.get("published_at"))
            if date_from and pub_date and pub_date < date_from:
                continue
            if date_to and pub_date and pub_date > date_to:
                continue
            item.update({k: v for k, v in source_meta.items() if k not in item})
            all_items.append(item)

    def sort_key(item: dict) -> str:
        return item.get("published_at") or ""

    all_items.sort(key=sort_key, reverse=True)
    return all_items


def get_dimension_stats() -> dict[str, dict[str, Any]]:
    """Get statistics for all dimensions.

    Returns dict keyed by dimension with counts, source counts, latest date.
    """
    stats: dict[str, dict[str, Any]] = {}

    if not RAW_DATA_DIR.exists():
        return stats

    for dim_dir in RAW_DATA_DIR.iterdir():
        if not dim_dir.is_dir():
            continue

        dimension = dim_dir.name
        total_items = 0
        sources: set[str] = set()
        latest_date: str | None = None

        for json_file in dim_dir.rglob(LATEST_FILENAME):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                total_items += data.get("item_count", len(data.get("items", [])))
                sid = data.get("source_id")
                if sid:
                    sources.add(sid)
                crawled = data.get("crawled_at", "")
                if crawled and (not latest_date or crawled > latest_date):
                    latest_date = crawled
            except (json.JSONDecodeError, OSError):
                continue

        stats[dimension] = {
            "dimension": dimension,
            "total_items": total_items,
            "source_count": len(sources),
            "sources": sorted(sources),
            "latest_crawl": latest_date,
        }

    return stats


def get_all_articles(
    dimension: str | None = None,
    source_id: str | None = None,
    keyword: str | None = None,
    tags: list[str] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict[str, Any]]:
    """Read articles from all dimensions (or a specific one) with filtering.

    Scans data/raw/ for all latest.json files. Supports keyword search
    (title + content), tags overlap, source_id, and date range filtering.
    Returns a flat list of article dicts sorted by published_at desc.
    """
    if not RAW_DATA_DIR.exists():
        return []

    if dimension:
        dimensions = [dimension]
    else:
        dimensions = [
            d.name for d in RAW_DATA_DIR.iterdir() if d.is_dir()
        ]

    all_items: list[dict[str, Any]] = []
    keyword_lower = keyword.lower() if keyword else None

    for dim in dimensions:
        dim_dir = RAW_DATA_DIR / dim
        if not dim_dir.exists():
            continue

        for json_file in dim_dir.rglob(LATEST_FILENAME):
            rel = json_file.relative_to(dim_dir)
            parts = rel.parts

            if len(parts) == 3:
                file_group, file_source, _ = parts
            elif len(parts) == 2:
                file_group = None
                file_source, _ = parts
            else:
                continue

            if source_id and file_source != source_id:
                continue

            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read %s: %s", json_file, e)
                continue

            source_meta = {
                "source_id": data.get("source_id", file_source),
                "source_name": data.get("source_name", file_source),
                "dimension": data.get("dimension", dim),
                "group": data.get("group", file_group),
                "crawled_at": data.get("crawled_at"),
            }

            for item in data.get("items", []):
                # Date range filter
                pub_date = _parse_date(item.get("published_at"))
                if date_from and pub_date and pub_date < date_from:
                    continue
                if date_to and pub_date and pub_date > date_to:
                    continue

                # Keyword filter (title + content)
                if keyword_lower:
                    title = (item.get("title") or "").lower()
                    content = (item.get("content") or "").lower()
                    if keyword_lower not in title and keyword_lower not in content:
                        continue

                # Tags overlap filter
                if tags:
                    item_tags = item.get("tags") or []
                    if not set(tags) & set(item_tags):
                        continue

                item.update({k: v for k, v in source_meta.items() if k not in item})
                all_items.append(item)

    all_items.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return all_items


def get_available_dates(dimension: str) -> list[str]:
    """Get all available crawled_at dates for a dimension, sorted desc."""
    dim_dir = RAW_DATA_DIR / dimension
    if not dim_dir.exists():
        return []

    dates: set[str] = set()
    for json_file in dim_dir.rglob(LATEST_FILENAME):
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
            crawled_at = data.get("crawled_at")
            if crawled_at:
                d = _parse_date(crawled_at)
                if d:
                    dates.add(d.isoformat())
        except (json.JSONDecodeError, OSError):
            continue

    return sorted(dates, reverse=True)
