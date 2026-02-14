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


def _serialize_item(item: Any) -> dict[str, Any]:
    """Convert a CrawledItem to a JSON-serializable dict."""
    return {
        "title": item.title,
        "url": item.url,
        "url_hash": compute_url_hash(item.url),
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "author": item.author,
        "summary": item.summary,
        "content": item.content,
        "content_hash": item.content_hash,
        "source_id": item.source_id,
        "dimension": item.dimension,
        "tags": item.tags,
        "extra": item.extra,
    }


def save_crawl_result_json(
    result: Any,
    source_config: dict[str, Any],
) -> Path | None:
    """
    Save crawl result items to a daily JSON file.

    Output path: data/raw/{dimension}/{group}/{source_id}/{YYYY-MM-DD}.json
    If group is not set, falls back to: data/raw/{dimension}/{source_id}/{YYYY-MM-DD}.json

    If the file already exists (same day, multiple crawls), merges items
    by url_hash to avoid duplicates.

    Returns the path to the written file, or None if no items.
    """
    if not result.items:
        return None

    dimension = source_config.get("dimension", "unknown")
    group = source_config.get("group")
    source_id = source_config.get("id", "unknown")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if group:
        output_dir = DATA_DIR / dimension / group / source_id
    else:
        output_dir = DATA_DIR / dimension / source_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{today}.json"

    # Load existing data if file exists (merge with previous crawl of the same day)
    existing_items: dict[str, dict] = {}
    if output_file.exists():
        try:
            with open(output_file, encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("items", []):
                url_hash = item.get("url_hash")
                if url_hash:
                    existing_items[url_hash] = item
        except (json.JSONDecodeError, KeyError):
            logger.warning("Corrupted JSON file %s, will overwrite", output_file)

    # Add new items
    for item in result.items:
        serialized = _serialize_item(item)
        url_hash = serialized["url_hash"]
        if url_hash not in existing_items:
            existing_items[url_hash] = serialized

    # Write merged result
    output_data = {
        "source_id": source_id,
        "dimension": dimension,
        "group": group,
        "source_name": source_config.get("name", source_id),
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "item_count": len(existing_items),
        "items": list(existing_items.values()),
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    logger.info(
        "Saved %d items to %s (total in file: %d)",
        len(result.items),
        output_file,
        len(existing_items),
    )
    return output_file
