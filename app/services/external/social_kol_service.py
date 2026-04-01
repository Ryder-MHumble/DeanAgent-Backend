"""Unified social KOL storage service (cross-platform ready)."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

from app.config import BASE_DIR, settings
from app.db.client import get_client
from app.schemas.social_kol import (
    SocialAccountItem,
    SocialAccountListResponse,
    SocialIngestResponse,
    SocialPostDetailResponse,
    SocialPostItem,
    SocialPostListResponse,
    SocialTwitterIngestRequest,
)

logger = logging.getLogger(__name__)

# 每次仅入库每个账号最新 3 条帖子
DEFAULT_POSTS_PER_USER = 3
_TWITTER_API_BASE = "https://api.twitterapi.io/twitter"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_username(raw: Any) -> str:
    return str(raw or "").strip().lstrip("@").lower()


def _clean_username(raw: Any) -> str:
    return str(raw or "").strip().lstrip("@")


def _to_int(raw: Any) -> int:
    if raw is None:
        return 0
    try:
        return int(raw)
    except Exception:
        return 0


def _to_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return False
    text = str(raw).strip().lower()
    return text in {"1", "true", "yes", "y"}


def _parse_time(raw: Any) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).isoformat()
    except Exception:
        pass

    try:
        return datetime.strptime(
            str(raw).strip(),
            "%a %b %d %H:%M:%S %z %Y",
        ).isoformat()
    except Exception:
        return None


def _infer_post_type(type_value: Any, is_reply: Any, text: Any) -> str:
    t = str(type_value or "").strip().lower()
    if t in {"reply", "repost", "retweet", "quote", "comment"}:
        if t == "retweet":
            return "repost"
        return t
    if _to_bool(is_reply):
        return "reply"
    if str(text or "").strip().startswith("RT @"):
        return "repost"
    return "post"


def _normalize_top_replies(raw_replies: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_replies, list):
        return []

    out: list[dict[str, Any]] = []
    for raw in raw_replies:
        if not isinstance(raw, dict):
            continue

        author = raw.get("author") if isinstance(raw.get("author"), dict) else {}
        out.append(
            {
                "id": str(raw.get("id") or "").strip() or None,
                "createdAt": raw.get("createdAt"),
                "text": raw.get("text"),
                "url": raw.get("url") or raw.get("twitterUrl"),
                "likeCount": _to_int(raw.get("likeCount")),
                "retweetCount": _to_int(raw.get("retweetCount")),
                "replyCount": _to_int(raw.get("replyCount")),
                "quoteCount": _to_int(raw.get("quoteCount")),
                "viewCount": _to_int(raw.get("viewCount")),
                "bookmarkCount": _to_int(raw.get("bookmarkCount")),
                "lang": raw.get("lang"),
                "isReply": _to_bool(raw.get("isReply")),
                "author": {
                    "username": author.get("userName"),
                    "name": author.get("name"),
                    "id": author.get("id"),
                },
            }
        )
    return out


def _resolve_accounts_file(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    under_sources = settings.SOURCES_DIR / path
    if under_sources.exists():
        return under_sources
    return BASE_DIR / path


def _load_twitter_accounts(
    *,
    accounts_file: str,
    cohort: str = "all",
) -> list[dict[str, Any]]:
    resolved = _resolve_accounts_file(accounts_file)
    if not resolved.exists():
        return []

    raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    accounts = raw.get("accounts", []) if isinstance(raw, dict) else []
    parsed: list[dict[str, Any]] = []
    cohort_key = str(cohort or "all").strip().lower()

    for item in accounts:
        if not isinstance(item, dict):
            continue
        username = _clean_username(item.get("username"))
        if not username:
            continue
        item_cohort = str(item.get("cohort") or "").strip().lower() or "core"
        if cohort_key != "all" and item_cohort != cohort_key:
            continue
        parsed.append(
            {
                "username": username,
                "name": str(item.get("name") or username).strip(),
                "category": str(item.get("category") or "").strip() or None,
                "cohort": item_cohort,
            }
        )

    dedup: dict[str, dict[str, Any]] = {}
    for item in parsed:
        key = item["username"].lower()
        dedup.setdefault(key, item)
    return list(dedup.values())


async def _fetch_twitter_user_posts(
    client: httpx.AsyncClient,
    *,
    username: str,
    max_posts: int,
    include_replies: bool,
) -> dict[str, Any] | None:
    resp = await client.get(
        f"{_TWITTER_API_BASE}/user/last_tweets",
        params={
            "userName": username,
            "includeReplies": "true" if include_replies else "false",
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "success":
        return None

    data_block = payload.get("data")
    tweets: list[dict[str, Any]] = []
    if isinstance(data_block, dict):
        raw_tweets = data_block.get("tweets", [])
        if isinstance(raw_tweets, list):
            tweets = [x for x in raw_tweets if isinstance(x, dict)]
    tweets = tweets[:max_posts]

    author = (tweets[0].get("author") or {}) if tweets else {}
    matched_username = _clean_username(author.get("userName") or username)
    display_name = str(author.get("name") or "").strip() or None
    return {
        "query_username": username,
        "matched_username": matched_username or username,
        "display_name": display_name,
        "latest_5_posts": tweets,
    }


async def crawl_and_ingest_twitter_source(source_config: dict[str, Any]) -> SocialIngestResponse:
    """Fetch twitterapi.io data by source YAML config and ingest into social tables."""
    platform = "x"
    accounts_file = str(source_config.get("twitter_accounts_file") or "").strip()
    if not accounts_file:
        raise ValueError("twitter_accounts_file is not configured")
    if not settings.TWITTER_API_KEY:
        raise RuntimeError("TWITTER_API_KEY is not configured")

    cohort = str(source_config.get("crawl_accounts_cohort") or "all").strip().lower()
    max_posts = max(1, int(source_config.get("max_tweets_per_account", DEFAULT_POSTS_PER_USER) or 3))
    include_replies = bool(source_config.get("include_replies", True))
    reply_limit = max(0, int(source_config.get("max_replies_per_post", 5) or 5))
    timeout = float(source_config.get("twitter_request_timeout_seconds", 45) or 45)

    accounts = _load_twitter_accounts(accounts_file=accounts_file, cohort=cohort)
    if not accounts:
        logger.warning("Twitter KOL social ingest: no accounts selected for cohort=%s", cohort)
        return SocialIngestResponse(
            platform=platform,
            users=0,
            kol_accounts_upserted=0,
            accounts_upserted=0,
            posts_upserted=0,
            skipped_posts=0,
        )

    headers = {"x-api-key": settings.TWITTER_API_KEY, "Accept": "application/json"}
    users: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    async def _run_fetch(proxy: str | None, target_accounts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        ok: list[dict[str, Any]] = []
        fail: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=timeout, headers=headers, proxy=proxy) as client:
            for account in target_accounts:
                username = account["username"]
                try:
                    block = await _fetch_twitter_user_posts(
                        client,
                        username=username,
                        max_posts=max_posts,
                        include_replies=include_replies,
                    )
                    if not block:
                        fail.append(account)
                        continue
                    block["category"] = account.get("category")
                    block["cohort"] = account.get("cohort")
                    ok.append(block)
                except Exception:
                    fail.append(account)
        return ok, fail

    ok1, fail1 = await _run_fetch(settings.TWITTER_API_PROXY or None, accounts)
    users.extend(ok1)
    failed.extend(fail1)

    # 代理失败时自动降级直连重试，提升稳定性。
    if failed and settings.TWITTER_API_PROXY:
        ok2, fail2 = await _run_fetch(None, failed)
        users.extend(ok2)
        failed = fail2

    fetched_at_utc = datetime.now(timezone.utc).isoformat()
    payload = SocialTwitterIngestRequest.model_validate(
        {
            "platform": platform,
            "fetched_at_utc": fetched_at_utc,
            "max_posts_per_user": max_posts,
            "top_replies_per_post": reply_limit,
            "include_replies": include_replies,
            "users": users,
        }
    )
    result = await ingest_twitter_bundle(payload)
    logger.info(
        "Twitter KOL social ingest done: users=%d failed=%d posts_upserted=%d skipped=%d",
        len(users),
        len(failed),
        result.posts_upserted,
        result.skipped_posts,
    )
    return result


async def _upsert_account(
    *,
    platform: str,
    username: str,
    display_name: str | None = None,
    platform_user_id: str | None = None,
    profile_url: str | None = None,
    avatar_url: str | None = None,
    bio: str | None = None,
    follower_count: int = 0,
    following_count: int = 0,
    post_count: int = 0,
    is_verified: bool = False,
    is_kol: bool = False,
    metadata: dict[str, Any] | None = None,
    raw_profile: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    clean = _clean_username(username)
    normalized = _norm_username(username)
    if not clean or not normalized:
        return None

    now_iso = _now_iso()
    row = {
        "platform": platform,
        "username": clean,
        "username_normalized": normalized,
        "display_name": display_name,
        "platform_user_id": platform_user_id,
        "profile_url": profile_url,
        "avatar_url": avatar_url,
        "bio": bio,
        "follower_count": _to_int(follower_count),
        "following_count": _to_int(following_count),
        "post_count": _to_int(post_count),
        "is_verified": _to_bool(is_verified),
        "is_kol": _to_bool(is_kol),
        "metadata": metadata or {},
        "raw_profile": raw_profile or {},
        "first_seen_at": now_iso,
        "last_seen_at": now_iso,
        "updated_at": now_iso,
    }

    db = get_client()
    res = await (
        db.table("social_accounts")
        .upsert(row, on_conflict="platform,username_normalized")
        .execute()
    )
    if res.data:
        return dict(res.data[0])

    fallback = await (
        db.table("social_accounts")
        .select("*")
        .eq("platform", platform)
        .eq("username_normalized", normalized)
        .limit(1)
        .execute()
    )
    if fallback.data:
        return dict(fallback.data[0])
    return None


async def _post_exists(platform: str, external_post_id: str) -> bool:
    db = get_client()
    res = await (
        db.table("social_posts")
        .select("id")
        .eq("platform", platform)
        .eq("external_post_id", external_post_id)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def _build_post_row(
    *,
    platform: str,
    raw: dict[str, Any],
    account_id: int | None,
    author_username: str,
    author_display_name: str | None,
    author_platform_user_id: str | None,
    is_kol_author: bool,
    crawled_at: str | None,
    include_replies: bool,
    top_replies_per_post: int,
) -> dict[str, Any] | None:
    external_post_id = str(raw.get("id") or "").strip()
    if not external_post_id:
        return None

    post_type = _infer_post_type(
        raw.get("type"),
        raw.get("isReply"),
        raw.get("text"),
    )

    top_replies: list[dict[str, Any]] = []
    if include_replies:
        top_replies = _normalize_top_replies(
            raw.get("top_5_hot_replies")
            or raw.get("top_5_replies")
            or raw.get("topReplies")
            or raw.get("replies")
            or []
        )
        if top_replies_per_post >= 0:
            top_replies = top_replies[:top_replies_per_post]

    return {
        "platform": platform,
        "external_post_id": external_post_id,
        "account_id": account_id,
        "author_username": author_username,
        "author_display_name": author_display_name,
        "author_platform_user_id": author_platform_user_id,
        "is_kol_author": _to_bool(is_kol_author),
        "post_type": post_type,
        "content_text": raw.get("text"),
        "content_lang": raw.get("lang"),
        # 保留一个链接字段即可
        "post_url": raw.get("url") or raw.get("twitterUrl"),
        "published_at": _parse_time(raw.get("createdAt")),
        "crawled_at": crawled_at or _now_iso(),
        "like_count": _to_int(raw.get("likeCount")),
        "reply_count": _to_int(raw.get("replyCount")),
        "repost_count": _to_int(raw.get("retweetCount")),
        "quote_count": _to_int(raw.get("quoteCount")),
        "view_count": _to_int(raw.get("viewCount")),
        "bookmark_count": _to_int(raw.get("bookmarkCount")),
        "top_replies": top_replies,
        "top_replies_count": len(top_replies),
        "extra": {
            k: raw.get(k)
            for k in ("source", "replies_query", "replies_query_type")
            if raw.get(k) is not None
        },
        "raw_payload": raw,
        "updated_at": _now_iso(),
    }


async def ingest_twitter_bundle(payload: SocialTwitterIngestRequest) -> SocialIngestResponse:
    """Ingest twitterapi.io aggregated payload into unified tables."""
    platform = (payload.platform or "x").strip().lower()
    users = payload.users or []
    max_posts_per_user = max(1, int(payload.max_posts_per_user or DEFAULT_POSTS_PER_USER))
    top_replies_per_post = max(0, int(payload.top_replies_per_post or 0))
    include_replies = bool(payload.include_replies)

    db = get_client()

    kol_usernames: set[str] = set()
    for user in users:
        matched = _norm_username(user.get("matched_username"))
        query = _norm_username(user.get("query_username"))
        if matched:
            kol_usernames.add(matched)
        elif query:
            kol_usernames.add(query)

    account_keys_seen: set[tuple[str, str]] = set()
    kol_account_keys_seen: set[tuple[str, str]] = set()
    posts_inserted = 0
    skipped_posts = 0

    crawled_at = _parse_time(payload.fetched_at_utc) if payload.fetched_at_utc else _now_iso()

    for user in users:
        query_username = _clean_username(user.get("query_username"))
        matched_username = _clean_username(user.get("matched_username")) or query_username
        kol_norm = _norm_username(matched_username)
        display_name = user.get("display_name")

        kol_account = await _upsert_account(
            platform=platform,
            username=matched_username,
            display_name=display_name,
            profile_url=f"https://x.com/{matched_username}" if matched_username else None,
            is_kol=True,
            metadata={
                "display_name": display_name,
                "query_username": query_username,
                "matched_username": matched_username,
            },
        )
        if kol_account and kol_norm:
            key = (platform, kol_norm)
            account_keys_seen.add(key)
            kol_account_keys_seen.add(key)

        posts = user.get("latest_5_posts") or user.get("top_5_posts") or []
        if not isinstance(posts, list):
            continue

        # 只写每个账号最新 3 条
        for raw_post in posts[:max_posts_per_user]:
            if not isinstance(raw_post, dict):
                skipped_posts += 1
                continue

            post_author = raw_post.get("author") if isinstance(raw_post.get("author"), dict) else {}
            post_author_username = _clean_username(
                post_author.get("userName") or matched_username or query_username
            )
            post_author_norm = _norm_username(post_author_username)
            if not post_author_norm:
                skipped_posts += 1
                continue

            post_author_account = await _upsert_account(
                platform=platform,
                username=post_author_username,
                display_name=post_author.get("name") or display_name,
                platform_user_id=(str(post_author.get("id")) if post_author.get("id") else None),
                profile_url=post_author.get("url"),
                avatar_url=post_author.get("profilePicture"),
                bio=post_author.get("description"),
                follower_count=_to_int(post_author.get("followers")),
                following_count=_to_int(post_author.get("following")),
                post_count=_to_int(post_author.get("statusesCount")),
                is_verified=_to_bool(post_author.get("isBlueVerified")),
                is_kol=(post_author_norm in kol_usernames),
                metadata={"ingested_from": "twitter_bundle"},
                raw_profile=post_author,
            )
            account_keys_seen.add((platform, post_author_norm))
            if post_author_norm in kol_usernames:
                kol_account_keys_seen.add((platform, post_author_norm))

            row = _build_post_row(
                platform=platform,
                raw=raw_post,
                account_id=(int(post_author_account["id"]) if post_author_account else None),
                author_username=post_author_username,
                author_display_name=post_author.get("name") or display_name,
                author_platform_user_id=(
                    str(post_author.get("id")) if post_author.get("id") else None
                ),
                is_kol_author=(post_author_norm in kol_usernames),
                crawled_at=crawled_at,
                include_replies=include_replies,
                top_replies_per_post=top_replies_per_post,
            )
            if not row:
                skipped_posts += 1
                continue

            # 去重：重复帖子直接跳过，不重复写入
            exists = await _post_exists(platform, row["external_post_id"])
            if exists:
                skipped_posts += 1
                continue

            await db.table("social_posts").insert(row).execute()
            posts_inserted += 1

    return SocialIngestResponse(
        platform=platform,
        users=len(users),
        kol_accounts_upserted=len(kol_account_keys_seen),
        accounts_upserted=len(account_keys_seen),
        posts_upserted=posts_inserted,
        skipped_posts=skipped_posts,
    )


async def list_accounts(
    *,
    platform: str | None = None,
    keyword: str | None = None,
    is_kol: bool | None = None,
    sort_by: str = "last_seen_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> SocialAccountListResponse:
    db = get_client()
    query = db.table("social_accounts").select("*", count="exact")

    if platform:
        query = query.eq("platform", platform.strip().lower())
    if is_kol is not None:
        query = query.eq("is_kol", is_kol)
    if keyword:
        kw = str(keyword).strip()
        if kw:
            query = query.or_(
                f"username.ilike.%{kw}%,display_name.ilike.%{kw}%,bio.ilike.%{kw}%"
            )

    desc = str(sort_order).lower() != "asc"
    query = query.order(sort_by, desc=desc)

    offset = (page - 1) * page_size
    query = query.range(offset, offset + page_size - 1)

    res = await query.execute()
    total = int(res.count or 0)
    items = [SocialAccountItem(**dict(row)) for row in (res.data or [])]
    return SocialAccountListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
        items=items,
    )


async def list_posts(
    *,
    platform: str | None = None,
    username: str | None = None,
    post_type: str | None = "post",
    is_kol_author: bool | None = True,
    keyword: str | None = None,
    sort_by: str = "published_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
    include_top_replies: bool = False,
    top_replies_limit: int = 5,
) -> SocialPostListResponse:
    db = get_client()
    query = db.table("social_posts").select("*", count="exact")

    if platform:
        query = query.eq("platform", platform.strip().lower())
    if username:
        # 只保留 author_username 字段后，使用 ILIKE 做大小写无关匹配
        query = query.ilike("author_username", _clean_username(username))
    if post_type:
        query = query.eq("post_type", post_type)
    if is_kol_author is not None:
        query = query.eq("is_kol_author", is_kol_author)
    if keyword:
        kw = str(keyword).strip()
        if kw:
            query = query.or_(
                f"content_text.ilike.%{kw}%,author_display_name.ilike.%{kw}%,"
                f"author_username.ilike.%{kw}%"
            )

    desc = str(sort_order).lower() != "asc"
    query = query.order(sort_by, desc=desc).order("created_at", desc=True)

    offset = (page - 1) * page_size
    query = query.range(offset, offset + page_size - 1)

    res = await query.execute()
    total = int(res.count or 0)
    items = [SocialPostItem(**dict(row)) for row in (res.data or [])]

    if not include_top_replies:
        for item in items:
            item.top_replies = []
            item.top_replies_count = 0
    else:
        for item in items:
            item.top_replies = item.top_replies[:top_replies_limit]
            item.top_replies_count = len(item.top_replies)

    return SocialPostListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
        items=items,
    )


async def get_post_detail(
    *,
    platform: str,
    external_post_id: str,
    top_replies_limit: int = 5,
) -> SocialPostDetailResponse | None:
    db = get_client()
    res = await (
        db.table("social_posts")
        .select("*")
        .eq("platform", platform.strip().lower())
        .eq("external_post_id", external_post_id.strip())
        .limit(1)
        .execute()
    )
    if not res.data:
        return None

    post = SocialPostItem(**dict(res.data[0]))
    post.top_replies = post.top_replies[:top_replies_limit]
    post.top_replies_count = len(post.top_replies)
    return SocialPostDetailResponse(post=post)
