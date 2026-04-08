from __future__ import annotations

import json
import logging
import math
import re
from datetime import datetime
from threading import Lock
from typing import Any

from app.config import BASE_DIR
from app.schemas.article import ArticleSearchParams, ArticleUpdate
from app.schemas.common import PaginatedResponse
from app.services.intel.shared import parse_source_filter
from app.services.stores.json_reader import get_all_articles, get_all_articles_paginated

logger = logging.getLogger(__name__)

_ALLOWED_SORT_FIELDS = {"crawled_at", "published_at", "title", "importance"}
_SOCIAL_SOURCE_ID_BY_PLATFORM = {
    "x": "twitter_ai_kol_international",
}
_COVER_IMAGE_FIELD_KEYS = (
    "thumbnail",
    "thumb",
    "image",
    "image_url",
    "cover",
    "cover_image",
    "cover_image_url",
    "hero_image",
    "banner",
    "banner_image",
)
_IMAGE_URL_PATTERN = re.compile(
    r"https?://[^\s\"'<>]+?\.(?:png|jpe?g|webp|gif|bmp|svg)(?:\?[^\s\"'<>]*)?",
    re.IGNORECASE,
)
_IMG_TAG_SRC_PATTERN = re.compile(
    r"<img[^>]+src=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)

# Article annotations (is_read, importance) stored in a simple JSON file
# Used as fallback when DB is not available.
ANNOTATIONS_FILE = BASE_DIR / "data" / "state" / "article_annotations.json"
_annotations_lock = Lock()


def _social_article_id(platform: str, external_post_id: str) -> str:
    return f"social:{platform}:{external_post_id}"


def _is_social_article_id(article_id: str) -> bool:
    return str(article_id or "").startswith("social:")


def _parse_social_article_id(article_id: str) -> tuple[str, str] | None:
    text = str(article_id or "")
    if not text.startswith("social:"):
        return None
    parts = text.split(":", 2)
    if len(parts) != 3:
        return None
    platform = parts[1].strip().lower()
    external_post_id = parts[2].strip()
    if not platform or not external_post_id:
        return None
    return platform, external_post_id


def _platform_to_article_dimension(platform: str) -> str:
    if platform == "x":
        return "twitter"
    return "social"


def _platform_to_source_name(platform: str) -> str:
    mapping = {
        "x": "Twitter",
        "youtube": "YouTube",
        "linkedin": "LinkedIn",
        "xiaoyuzhou": "小宇宙",
    }
    return mapping.get(platform, platform)


def _should_include_social_items(
    *,
    dimension: str | None,
    source_filter: set[str] | None,
) -> bool:
    """Whether current query should merge social_posts into article feed."""
    social_source_ids = set(_SOCIAL_SOURCE_ID_BY_PLATFORM.values())

    if dimension and dimension.lower() not in {"twitter", "social"}:
        return bool(source_filter and (social_source_ids & source_filter))
    if source_filter is not None:
        return bool(social_source_ids & source_filter)
    return True


def _social_row_to_article_item(row: dict[str, Any]) -> dict[str, Any]:
    platform = str(row.get("platform") or "").strip().lower()
    external_post_id = str(row.get("external_post_id") or "").strip()
    source_id = _SOCIAL_SOURCE_ID_BY_PLATFORM.get(platform, f"social_{platform}")
    source_name = _platform_to_source_name(platform)

    content_text = str(row.get("content_text") or "")
    title = content_text.strip().replace("\n", " ")
    if len(title) > 120:
        title = title[:120] + "..."
    if not title:
        title = f"{source_name} post {external_post_id}"

    username = str(row.get("author_username") or "").strip()
    display = str(row.get("author_display_name") or "").strip()
    author = display or username or None
    if display and username:
        author = f"{display} (@{username})"

    top_replies = row.get("top_replies")
    top_replies_count = (
        len(top_replies) if isinstance(top_replies, list) else int(row.get("top_replies_count") or 0)
    )
    tags = [
        "social",
        platform,
        f"type:{row.get('post_type') or 'post'}",
    ]
    if username:
        tags.append(f"@{username}")

    return {
        "url_hash": _social_article_id(platform, external_post_id),
        "source_id": source_id,
        "source_name": source_name,
        "dimension": _platform_to_article_dimension(platform),
        "group": "social_kol",
        "url": row.get("post_url"),
        "title": title,
        "author": author,
        "published_at": row.get("published_at"),
        "crawled_at": row.get("crawled_at") or row.get("created_at"),
        "tags": tags,
        "content": row.get("content_text"),
        "content_html": None,
        "extra": {
            "platform": platform,
            "external_post_id": external_post_id,
            "post_type": row.get("post_type"),
            "author_username": row.get("author_username"),
            "author_display_name": row.get("author_display_name"),
            "is_kol_author": row.get("is_kol_author"),
            "post_url": row.get("post_url"),
            "like_count": row.get("like_count", 0),
            "reply_count": row.get("reply_count", 0),
            "repost_count": row.get("repost_count", 0),
            "quote_count": row.get("quote_count", 0),
            "view_count": row.get("view_count", 0),
            "bookmark_count": row.get("bookmark_count", 0),
            "top_replies_count": top_replies_count,
            "top_replies": top_replies if isinstance(top_replies, list) else [],
            "is_social_post": True,
        },
        "custom_fields": {
            "platform": platform,
            "post_type": str(row.get("post_type") or "post"),
            "top_replies_count": str(top_replies_count),
        },
    }


async def _get_social_article_items(
    *,
    dimension: str | None = None,
    source_filter: set[str] | None = None,
    keyword: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[dict[str, Any]]:
    if dimension and dimension.lower() not in {"twitter", "social"}:
        return []
    if source_filter is not None and not source_filter:
        return []

    social_source_ids = set(_SOCIAL_SOURCE_ID_BY_PLATFORM.values())
    if source_filter is not None and not (social_source_ids & source_filter):
        return []

    try:
        from app.db.client import get_client  # noqa: PLC0415

        client = get_client()
        query = client.table("social_posts").select("*").order("published_at", desc=True)

        if dimension and dimension.lower() == "twitter":
            query = query.eq("platform", "x")
        if keyword:
            query = query.or_(
                f"content_text.ilike.%{keyword}%,author_display_name.ilike.%{keyword}%,"
                f"author_username.ilike.%{keyword}%"
            )
        if date_from is not None:
            query = query.gte("published_at", date_from.isoformat())
        if date_to is not None:
            query = query.lte("published_at", date_to.isoformat())

        res = await query.execute()
        rows = res.data or []
        return [_social_row_to_article_item(row) for row in rows]
    except RuntimeError:
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning("DB social_posts query failed, skipping social posts: %s", exc)
        return []


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
    """Merge annotations (is_read, importance) into an article item.

    If the item already has is_read/importance (from DB), these take precedence.
    Falls back to the JSON annotations file.
    """
    # If item already has annotations from DB, trust them
    if "is_read" in item and "importance" in item:
        return item

    url_hash = item.get("url_hash", "")
    if not url_hash:
        item.setdefault("is_read", False)
        item.setdefault("importance", None)
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
    """Convert a raw article item to ArticleBrief-compatible dict."""
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
        "cover_image_url": _extract_cover_image_url(item),
        "custom_fields": item.get("custom_fields") or {},
    }


def _is_http_url(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def _first_image_in_value(value: Any) -> str | None:
    if _is_http_url(value):
        return value

    if isinstance(value, list):
        for entry in value:
            image_url = _first_image_in_value(entry)
            if image_url:
                return image_url
        return None

    if isinstance(value, dict):
        for key in ("src", "url"):
            maybe_url = value.get(key)
            if _is_http_url(maybe_url):
                return maybe_url
    return None


def _first_image_from_mapping(mapping: Any) -> str | None:
    if not isinstance(mapping, dict):
        return None

    for key in _COVER_IMAGE_FIELD_KEYS:
        image_url = _first_image_in_value(mapping.get(key))
        if image_url:
            return image_url

    image_url = _first_image_in_value(mapping.get("images"))
    if image_url:
        return image_url
    return None


def _extract_image_from_text(content: Any) -> str | None:
    if not isinstance(content, str) or not content:
        return None
    img_match = _IMG_TAG_SRC_PATTERN.search(content)
    if img_match and _is_http_url(img_match.group(1)):
        return img_match.group(1)
    url_match = _IMAGE_URL_PATTERN.search(content)
    if url_match:
        return url_match.group(0)
    return None


def _extract_cover_image_url(item: dict[str, Any]) -> str | None:
    for key in _COVER_IMAGE_FIELD_KEYS:
        image_url = _first_image_in_value(item.get(key))
        if image_url:
            return image_url

    for field in ("extra", "custom_fields"):
        image_url = _first_image_from_mapping(item.get(field))
        if image_url:
            return image_url

    for field in ("content_html", "content"):
        image_url = _extract_image_from_text(item.get(field))
        if image_url:
            return image_url
    return None


def _to_detail(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw article item to ArticleDetail-compatible dict."""
    brief = _to_brief(item)
    brief["content"] = item.get("content")
    brief["content_html"] = item.get("content_html")
    brief["extra"] = item.get("extra", {})
    return brief


async def list_articles(params: ArticleSearchParams) -> PaginatedResponse:
    """List articles with filtering, sorting, and pagination."""
    date_from = None
    date_to = None
    social_date_from = None
    social_date_to = None
    if params.date_from:
        if isinstance(params.date_from, datetime):
            date_from = params.date_from.date()
            social_date_from = params.date_from
        elif isinstance(params.date_from, str):
            try:
                dt = datetime.fromisoformat(params.date_from)
                date_from = dt.date()
                social_date_from = dt
            except ValueError:
                pass
    if params.date_to:
        if isinstance(params.date_to, datetime):
            date_to = params.date_to.date()
            social_date_to = params.date_to
        elif isinstance(params.date_to, str):
            try:
                dt = datetime.fromisoformat(params.date_to)
                date_to = dt.date()
                social_date_to = dt
            except ValueError:
                pass

    # 应用信源筛选（优先筛选，减少后续处理量）
    source_filter = parse_source_filter(
        params.source_id, params.source_ids, params.source_name, params.source_names
    )

    include_social_items = _should_include_social_items(
        dimension=params.dimension,
        source_filter=source_filter,
    )
    sort_field = params.sort_by if params.sort_by in _ALLOWED_SORT_FIELDS else "crawled_at"
    reverse = params.order != "asc"
    offset = (params.page - 1) * params.page_size

    can_use_db_pagination = not include_social_items and not params.custom_field_key
    if can_use_db_pagination:
        query_source_ids: list[str] | None
        if source_filter is None:
            query_source_ids = [params.source_id] if params.source_id else None
        else:
            query_source_ids = sorted(source_filter)

        try:
            rows, total = await get_all_articles_paginated(
                dimension=params.dimension,
                source_ids=query_source_ids,
                keyword=params.keyword,
                tags=params.tags,
                date_from=date_from,
                date_to=date_to,
                sort_by=sort_field,
                order=params.order,
                limit=params.page_size,
                offset=offset,
            )
            page_items = [_to_brief(item) for item in rows]
            return PaginatedResponse(
                items=page_items,
                total=total,
                page=params.page,
                page_size=params.page_size,
                total_pages=math.ceil(total / params.page_size) if params.page_size else 0,
            )
        except RuntimeError:
            logger.info("DB pagination unavailable, falling back to in-memory article listing")
        except Exception as exc:  # noqa: BLE001
            logger.warning("DB pagination failed, falling back to in-memory listing: %s", exc)

    # fallback path: full fetch + in-memory merge/filter/sort/pagination
    # If there is source_filter, avoid pushing source_id to DB query and filter later.
    items = await get_all_articles(
        dimension=params.dimension,
        source_id=None if source_filter is not None else params.source_id,
        keyword=params.keyword,
        tags=params.tags,
        date_from=date_from,
        date_to=date_to,
    )

    if include_social_items:
        social_items = await _get_social_article_items(
            dimension=params.dimension,
            source_filter=source_filter,
            keyword=params.keyword,
            date_from=social_date_from,
            date_to=social_date_to,
        )
        if social_items:
            items.extend(social_items)

    if source_filter is not None:
        items = [item for item in items if item.get("source_id") in source_filter]

    if params.custom_field_key:
        items = [
            item for item in items
            if (item.get("custom_fields") or {}).get(params.custom_field_key)
            == params.custom_field_value
        ]

    briefs = [_to_brief(item) for item in items]
    briefs.sort(key=lambda x: x.get(sort_field) or "", reverse=reverse)
    total = len(briefs)
    page_items = briefs[offset: offset + params.page_size]

    return PaginatedResponse(
        items=page_items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=math.ceil(total / params.page_size) if params.page_size else 0,
    )


async def get_article(article_id: str) -> dict[str, Any] | None:
    """Get a single article by url_hash."""
    social_id = _parse_social_article_id(article_id)
    if social_id is not None:
        platform, external_post_id = social_id
        try:
            from app.db.client import get_client  # noqa: PLC0415

            client = get_client()
            res = await (
                client.table("social_posts")
                .select("*")
                .eq("platform", platform)
                .eq("external_post_id", external_post_id)
                .limit(1)
                .execute()
            )
            if res.data:
                return _to_detail(_social_row_to_article_item(res.data[0]))
        except RuntimeError:
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("DB get social article failed: %s", exc)
            return None

    # Try DB first for efficiency
    try:
        from app.db.client import get_client  # noqa: PLC0415

        client = get_client()
        res = await client.table("articles").select("*").eq("url_hash", article_id).execute()
        if res.data:
            row = res.data[0]
            if "group_name" in row:
                row["group"] = row.pop("group_name")
            return _to_detail(row)
    except RuntimeError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("DB get_article failed: %s", exc)

    items = await get_all_articles()
    for item in items:
        if item.get("url_hash") == article_id:
            return _to_detail(item)

    social_items = await _get_social_article_items()
    for item in social_items:
        if item.get("url_hash") == article_id:
            return _to_detail(item)
    return None


async def update_article(article_id: str, data: ArticleUpdate) -> dict[str, Any] | None:
    """Update article annotations (is_read, importance).

    Writes to the DB when available, and always keeps the JSON fallback in sync.
    """
    values = data.model_dump(exclude_unset=True)
    if not values:
        return await get_article(article_id)

    # Try to update in DB
    db_updated = False
    try:
        from app.db.client import get_client  # noqa: PLC0415

        client = get_client()
        update_data = {k: v for k, v in values.items() if k in ("is_read", "importance")}

        # custom_fields shallow merge
        if "custom_fields" in values and values["custom_fields"] is not None:
            from app.services.core.custom_fields import merge_custom_fields  # noqa: PLC0415
            cur = await client.table("articles").select("custom_fields").eq(
                "url_hash", article_id
            ).execute()
            existing_cf = (cur.data[0].get("custom_fields") or {}) if cur.data else {}
            update_data["custom_fields"] = merge_custom_fields(existing_cf, values["custom_fields"])

        if update_data:
            await client.table("articles").update(update_data).eq("url_hash", article_id).execute()
            db_updated = True
    except RuntimeError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("DB update_article failed: %s", exc)

    # Always keep JSON annotations in sync (serves as backup / offline fallback)
    with _annotations_lock:
        annotations = _load_annotations()
        ann = annotations.setdefault(article_id, {})
        ann.update(values)
        _save_annotations(annotations)

    if db_updated:
        logger.debug("Updated article %s in DB and annotations JSON", article_id)

    return await get_article(article_id)


async def get_article_stats(group_by: str = "dimension") -> list[dict]:
    """Get article counts grouped by dimension, source, or day."""
    items = await get_all_articles()
    social_items = await _get_social_article_items()
    if social_items:
        items.extend(social_items)

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
