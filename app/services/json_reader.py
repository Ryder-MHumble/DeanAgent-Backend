"""Read and aggregate crawled JSON data from data/raw/ directory."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.config import BASE_DIR

logger = logging.getLogger(__name__)

RAW_DATA_DIR = BASE_DIR / "data" / "raw"


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
    """
    Read articles from data/raw/{dimension}/ JSON files.

    Supports filtering by group, source_id, and date range.
    Returns a flat list of article dicts sorted by published_at desc.
    """
    dim_dir = RAW_DATA_DIR / dimension
    if not dim_dir.exists():
        logger.warning("Dimension directory not found: %s", dim_dir)
        return []

    all_items: list[dict[str, Any]] = []
    json_files = list(dim_dir.rglob("*.json"))

    for json_file in json_files:
        # Extract group from path: data/raw/{dim}/{group}/{source}/{date}.json
        rel = json_file.relative_to(dim_dir)
        parts = rel.parts

        if len(parts) == 3:
            file_group, file_source, _ = parts
        elif len(parts) == 2:
            file_group = None
            file_source, _ = parts
        else:
            continue

        # Filter by group
        if group and file_group != group:
            continue

        # Filter by source_id
        if source_id and file_source != source_id:
            continue

        # Filter by date range (from filename YYYY-MM-DD.json)
        file_date_str = json_file.stem
        try:
            file_date = date.fromisoformat(file_date_str)
        except ValueError:
            continue

        if date_from and file_date < date_from:
            continue
        if date_to and file_date > date_to:
            continue

        # Read and parse
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
            item.update({k: v for k, v in source_meta.items() if k not in item})
            all_items.append(item)

    # Sort by published_at desc (nulls last)
    def sort_key(item: dict) -> str:
        pa = item.get("published_at") or ""
        return pa

    all_items.sort(key=sort_key, reverse=True)
    return all_items


def get_dimension_stats() -> dict[str, dict[str, Any]]:
    """
    Get statistics for all dimensions.

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

        for json_file in dim_dir.rglob("*.json"):
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


def get_available_dates(dimension: str) -> list[str]:
    """Get all available dates for a dimension, sorted desc."""
    dim_dir = RAW_DATA_DIR / dimension
    if not dim_dir.exists():
        return []

    dates: set[str] = set()
    for json_file in dim_dir.rglob("*.json"):
        d = json_file.stem
        try:
            date.fromisoformat(d)
            dates.add(d)
        except ValueError:
            continue

    return sorted(dates, reverse=True)
