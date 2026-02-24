from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from threading import Lock
from typing import Any

from app.config import BASE_DIR
from app.schemas.article import ArticleSearchParams, ArticleUpdate
from app.schemas.common import PaginatedResponse
from app.services.json_reader import get_all_articles

logger = logging.getLogger(__name__)

_ALLOWED_SORT_FIELDS = {"crawled_at", "published_at", "title", "importance"}

# Article annotations (is_read, importance) stored in a simple JSON file
ANNOTATIONS_FILE = BASE_DIR / "data" / "state" / "article_annotations.json"
_annotations_lock = Lock()


def _load_annotations() -> dict[str, dict[str, Any]]:
    if not ANNOTATIONS_FILE.exists():
        return {}
    try:
        with open(ANNOTATIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_annotations(data: dict[str, dict[str, Any]]) -> None:
    ANNOTATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = ANNOTATIONS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(ANNOTATIONS_FILE)


def _apply_annotations(item: dict[str, Any]) -> dict[str, Any]:
    """Merge annotations (is_read, importance) into an article item."""
    url_hash = item.get("url_hash", "")
    if not url_hash:
        return item
    annotations = _load_annotations()
    ann = annotations.get(url_hash, {})
    if ann:
        item["is_read"] = ann.get("is_read", False)
        item["importance"] = ann.get("importance")
    else:
        item.setdefault("is_read", False)
        item.setdefault("importance", None)
    return item


def _to_brief(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw JSON article item to ArticleBrief-compatible dict."""
    item = _apply_annotations(item)
    return {
        "id": item.get("url_hash", ""),
        "source_id": item.get("source_id", ""),
        "dimension": item.get("dimension", ""),
        "url": item.get("url", ""),
        "title": item.get("title", ""),
        "author": item.get("author"),
        "published_at": item.get("published_at"),
        "crawled_at": item.get("crawled_at"),
        "tags": item.get("tags", []),
        "is_read": item.get("is_read", False),
        "importance": item.get("importance"),
    }


def _to_detail(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw JSON article item to ArticleDetail-compatible dict."""
    brief = _to_brief(item)
    brief["content"] = item.get("content")
    brief["content_html"] = item.get("content_html")
    brief["extra"] = item.get("extra", {})
    return brief


async def list_articles(params: ArticleSearchParams) -> PaginatedResponse:
    """List articles with filtering, sorting, and pagination."""
    date_from = None
    date_to = None
    if params.date_from:
        if isinstance(params.date_from, datetime):
            date_from = params.date_from.date()
        elif isinstance(params.date_from, str):
            try:
                date_from = datetime.fromisoformat(params.date_from).date()
            except ValueError:
                pass
    if params.date_to:
        if isinstance(params.date_to, datetime):
            date_to = params.date_to.date()
        elif isinstance(params.date_to, str):
            try:
                date_to = datetime.fromisoformat(params.date_to).date()
            except ValueError:
                pass

    items = get_all_articles(
        dimension=params.dimension,
        source_id=params.source_id,
        keyword=params.keyword,
        tags=params.tags,
        date_from=date_from,
        date_to=date_to,
    )

    # Apply annotations
    briefs = [_to_brief(item) for item in items]

    # Sorting
    sort_field = params.sort_by if params.sort_by in _ALLOWED_SORT_FIELDS else "crawled_at"
    reverse = params.order != "asc"
    briefs.sort(key=lambda x: x.get(sort_field) or "", reverse=reverse)

    # Pagination
    total = len(briefs)
    offset = (params.page - 1) * params.page_size
    page_items = briefs[offset : offset + params.page_size]

    return PaginatedResponse(
        items=page_items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=math.ceil(total / params.page_size) if params.page_size else 0,
    )


async def get_article(article_id: str) -> dict[str, Any] | None:
    """Get a single article by url_hash."""
    items = get_all_articles()
    for item in items:
        if item.get("url_hash") == article_id:
            return _to_detail(item)
    return None


async def update_article(article_id: str, data: ArticleUpdate) -> dict[str, Any] | None:
    """Update article annotations (is_read, importance)."""
    values = data.model_dump(exclude_unset=True)
    if not values:
        return await get_article(article_id)

    with _annotations_lock:
        annotations = _load_annotations()
        ann = annotations.setdefault(article_id, {})
        ann.update(values)
        _save_annotations(annotations)

    return await get_article(article_id)


async def get_article_stats(group_by: str = "dimension") -> list[dict]:
    """Get article counts grouped by dimension, source, or day."""
    items = get_all_articles()

    counts: dict[str, int] = {}
    for item in items:
        if group_by == "source":
            key = item.get("source_id", "unknown")
        elif group_by == "day":
            crawled = item.get("crawled_at") or ""
            key = crawled[:10] if crawled else "unknown"
        else:
            key = item.get("dimension", "unknown")
        counts[key] = counts.get(key, 0) + 1

    result = [{"group": k, "count": v} for k, v in counts.items()]
    result.sort(key=lambda x: x["count"], reverse=True)
    return result
