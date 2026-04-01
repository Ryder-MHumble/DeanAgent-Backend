from __future__ import annotations

from collections import Counter
from typing import Any

from app.schemas.common import PaginatedResponse
from app.schemas.social_post import SocialPostBrief, SocialPostDetail

_ALLOWED_SORT_FIELDS = {
    "published_at",
    "crawled_at",
    "like_count",
    "reply_count",
    "repost_count",
    "quote_count",
    "view_count",
    "bookmark_count",
    "created_at",
}
_SOURCE_ID_BY_PLATFORM = {
    "x": "twitter_ai_kol_international",
}
_PLATFORM_BY_SOURCE_ID = {source_id: platform for platform, source_id in _SOURCE_ID_BY_PLATFORM.items()}
_SOURCE_NAME_BY_PLATFORM = {
    "x": "Twitter",
    "youtube": "YouTube",
    "linkedin": "LinkedIn",
    "xiaoyuzhou": "小宇宙",
}


def _social_post_id(platform: str, external_post_id: str) -> str:
    return f"social:{platform}:{external_post_id}"


def _parse_social_post_id(post_id: str) -> tuple[str, str] | None:
    parts = str(post_id or "").split(":", 2)
    if len(parts) != 3 or parts[0] != "social":
        return None
    platform = parts[1].strip().lower()
    external_post_id = parts[2].strip()
    if not platform or not external_post_id:
        return None
    return platform, external_post_id


def _source_id(platform: str) -> str:
    return _SOURCE_ID_BY_PLATFORM.get(platform, f"social_{platform}")


def _source_name(platform: str) -> str:
    return _SOURCE_NAME_BY_PLATFORM.get(platform, platform)


def _platforms_from_source_filter(source_filter: set[str] | None) -> set[str] | None:
    if source_filter is None:
        return None
    return {platform for source_id, platform in _PLATFORM_BY_SOURCE_ID.items() if source_id in source_filter}


def _to_brief(row: dict[str, Any]) -> SocialPostBrief:
    platform = str(row.get("platform") or "").strip().lower()
    external_post_id = str(row.get("external_post_id") or "").strip()
    return SocialPostBrief(
        id=_social_post_id(platform, external_post_id),
        platform=platform,
        external_post_id=external_post_id,
        source_id=_source_id(platform),
        source_name=_source_name(platform),
        author_username=str(row.get("author_username") or ""),
        author_display_name=row.get("author_display_name"),
        post_type=str(row.get("post_type") or "post"),
        content_text=row.get("content_text"),
        post_url=row.get("post_url"),
        published_at=row.get("published_at"),
        crawled_at=row.get("crawled_at"),
        like_count=int(row.get("like_count") or 0),
        reply_count=int(row.get("reply_count") or 0),
        repost_count=int(row.get("repost_count") or 0),
        quote_count=int(row.get("quote_count") or 0),
        view_count=int(row.get("view_count") or 0),
        bookmark_count=int(row.get("bookmark_count") or 0),
        top_replies_count=int(row.get("top_replies_count") or 0),
    )


async def list_social_posts(
    *,
    source_filter: set[str] | None = None,
    platform: str | None = None,
    username: str | None = None,
    post_type: str | None = None,
    is_kol_author: bool | None = None,
    keyword: str | None = None,
    sort_by: str = "published_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[SocialPostBrief]:
    if source_filter is not None and not source_filter:
        return PaginatedResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)

    allowed_platforms = _platforms_from_source_filter(source_filter)
    if source_filter is not None and not allowed_platforms:
        return PaginatedResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)

    platform_value = platform.strip().lower() if platform else None
    if platform_value and allowed_platforms is not None and platform_value not in allowed_platforms:
        return PaginatedResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)

    safe_page = max(1, page)
    safe_page_size = max(1, min(page_size, 200))
    try:
        from app.db.client import get_client  # noqa: PLC0415

        client = get_client()
        query = client.table("social_posts").select("*", count="exact")

        if platform_value:
            query = query.eq("platform", platform_value)
        elif allowed_platforms is not None:
            if len(allowed_platforms) == 1:
                query = query.eq("platform", next(iter(allowed_platforms)))
            else:
                query = query.in_("platform", sorted(allowed_platforms))

        if username:
            query = query.ilike("author_username", username.strip().lstrip("@"))
        if post_type:
            query = query.eq("post_type", post_type)
        if is_kol_author is not None:
            query = query.eq("is_kol_author", is_kol_author)
        if keyword:
            kw = keyword.strip()
            if kw:
                query = query.or_(
                    f"content_text.ilike.%{kw}%,author_display_name.ilike.%{kw}%,"
                    f"author_username.ilike.%{kw}%"
                )

        sort_field = sort_by if sort_by in _ALLOWED_SORT_FIELDS else "published_at"
        desc = order != "asc"
        query = query.order(sort_field, desc=desc).order("created_at", desc=True)

        offset = (safe_page - 1) * safe_page_size
        query = query.range(offset, offset + safe_page_size - 1)

        res = await query.execute()
        rows = res.data or []
        items = [_to_brief(row) for row in rows]
        total = int(res.count or 0)
    except RuntimeError:
        return PaginatedResponse(
            items=[],
            total=0,
            page=safe_page,
            page_size=safe_page_size,
            total_pages=0,
        )

    total_pages = (total + safe_page_size - 1) // safe_page_size if safe_page_size else 0
    return PaginatedResponse(
        items=items,
        total=total,
        page=safe_page,
        page_size=safe_page_size,
        total_pages=total_pages,
    )


async def get_social_post(post_id: str, *, top_replies_limit: int = 5) -> SocialPostDetail | None:
    parsed = _parse_social_post_id(post_id)
    if parsed is None:
        return None
    platform, external_post_id = parsed

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
    except RuntimeError:
        return None
    if not res.data:
        return None

    row = dict(res.data[0])
    top_replies = row.get("top_replies") if isinstance(row.get("top_replies"), list) else []
    top_replies = top_replies[: max(0, top_replies_limit)]

    brief = _to_brief(row)
    return SocialPostDetail(
        **brief.model_dump(),
        top_replies=top_replies,
        extra={
            "platform": row.get("platform"),
            "is_kol_author": row.get("is_kol_author"),
            "content_lang": row.get("content_lang"),
            "author_platform_user_id": row.get("author_platform_user_id"),
        },
    )


async def get_social_post_stats(group_by: str = "platform") -> list[dict[str, Any]]:
    try:
        from app.db.client import get_client  # noqa: PLC0415

        client = get_client()
    except RuntimeError:
        return []

    if group_by == "source":
        res = await client.table("social_posts").select("platform").execute()
        rows = res.data or []
        counts: Counter[str] = Counter(
            _source_id(str(row.get("platform") or "").strip().lower()) for row in rows
        )
    elif group_by == "author":
        res = await client.table("social_posts").select("author_username").execute()
        rows = res.data or []
        counts = Counter(str(row.get("author_username") or "unknown") for row in rows)
    elif group_by == "post_type":
        res = await client.table("social_posts").select("post_type").execute()
        rows = res.data or []
        counts = Counter(str(row.get("post_type") or "post") for row in rows)
    elif group_by == "day":
        res = await client.table("social_posts").select("published_at").execute()
        rows = res.data or []
        counts = Counter(str(row.get("published_at") or "")[:10] or "unknown" for row in rows)
    else:
        res = await client.table("social_posts").select("platform").execute()
        rows = res.data or []
        counts = Counter(str(row.get("platform") or "unknown") for row in rows)

    result = [{"group": key, "count": value} for key, value in counts.items()]
    result.sort(key=lambda x: x["count"], reverse=True)
    return result
