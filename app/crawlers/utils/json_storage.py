"""Save crawl results to local JSON files organized by dimension and source."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import BASE_DIR
from app.crawlers.utils.dedup import compute_url_hash

logger = logging.getLogger(__name__)

DATA_DIR = BASE_DIR / "data" / "raw"

LATEST_FILENAME = "latest.json"


def build_source_dir(dimension: str, group: str | None, source_id: str) -> Path:
    """Build the directory path for a source's JSON data.

    Convention: data/raw/{dimension}/{group}/{source_id}/
    or data/raw/{dimension}/{source_id}/ if group is None.
    """
    if group:
        return DATA_DIR / dimension / group / source_id
    return DATA_DIR / dimension / source_id


def _serialize_item(item: Any, *, is_new: bool) -> dict[str, Any]:
    """Convert a CrawledItem to a JSON-serializable dict with is_new flag."""
    return {
        "title": item.title,
        "url": item.url,
        "url_hash": compute_url_hash(item.url),
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "author": item.author,
        "content": item.content,
        "content_html": item.content_html,
        "content_hash": item.content_hash,
        "source_id": item.source_id,
        "dimension": item.dimension,
        "tags": item.tags,
        "extra": item.extra,
        "is_new": is_new,
    }


def _load_previous_hashes(file_path: Path) -> tuple[set[str], str | None]:
    """Load url_hash set and crawled_at from previous latest.json.

    Returns (set_of_url_hashes, previous_crawled_at_str).
    """
    if not file_path.exists():
        return set(), None
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        hashes = {
            item["url_hash"]
            for item in data.get("items", [])
            if item.get("url_hash")
        }
        return hashes, data.get("crawled_at")
    except (json.JSONDecodeError, KeyError, OSError):
        logger.warning("Could not read previous %s, treating as first crawl", file_path)
        return set(), None


def save_crawl_result_json(
    result: Any,
    source_config: dict[str, Any],
) -> Path | None:
    """Save all crawl result items to latest.json, overwriting the previous file.

    Output path: data/raw/{dimension}/{group}/{source_id}/latest.json

    All items from the crawl are saved (pre-dedup). Each item is annotated
    with is_new=true/false by comparing against the previous latest.json.

    Returns the path to the written file, or None if no items.
    """
    all_items = getattr(result, "items_all", None) or result.items
    if not all_items:
        return None

    dimension = source_config.get("dimension", "unknown")
    group = source_config.get("group")
    source_id = source_config.get("id", "unknown")

    output_dir = build_source_dir(dimension, group, source_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / LATEST_FILENAME

    prev_hashes, prev_crawled_at = _load_previous_hashes(output_file)

    serialized_items = []
    new_count = 0
    for item in all_items:
        url_hash = compute_url_hash(item.url)
        is_new = url_hash not in prev_hashes
        if is_new:
            new_count += 1
        serialized_items.append(_serialize_item(item, is_new=is_new))

    now_iso = datetime.now(timezone.utc).isoformat()

    output_data = {
        "source_id": source_id,
        "dimension": dimension,
        "group": group,
        "source_name": source_config.get("name", source_id),
        "crawled_at": now_iso,
        "previous_crawled_at": prev_crawled_at,
        "item_count": len(serialized_items),
        "new_item_count": new_count,
        "items": serialized_items,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    logger.info(
        "Saved %d items (%d new) to %s",
        len(serialized_items),
        new_count,
        output_file,
    )
    return output_file
