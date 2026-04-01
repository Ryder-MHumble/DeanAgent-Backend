"""Schemas for unified multi-platform KOL social data APIs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SocialAccountItem(BaseModel):
    """Unified social account profile."""

    model_config = {"extra": "ignore"}

    id: int
    platform: str
    username: str
    username_normalized: str
    display_name: str | None = None
    platform_user_id: str | None = None
    profile_url: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0
    is_verified: bool = False
    is_kol: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SocialAccountListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[SocialAccountItem]


class SocialPostItem(BaseModel):
    """Unified post record (hot replies embedded in one row)."""

    model_config = {"extra": "ignore"}

    id: int
    platform: str
    external_post_id: str
    account_id: int | None = None
    author_username: str
    author_display_name: str | None = None
    author_platform_user_id: str | None = None
    is_kol_author: bool = False
    post_type: str = "post"
    content_text: str | None = None
    content_lang: str | None = None
    post_url: str | None = None
    published_at: str | None = None
    crawled_at: str | None = None
    like_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    quote_count: int = 0
    view_count: int = 0
    bookmark_count: int = 0
    top_replies: list[dict[str, Any]] = Field(default_factory=list)
    top_replies_count: int = 0
    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class SocialPostDetailResponse(BaseModel):
    """Post detail (top replies embedded in post.top_replies)."""

    post: SocialPostItem


class SocialPostListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[SocialPostItem]


class SocialTwitterIngestRequest(BaseModel):
    """Raw twitterapi.io-like payload for ingestion."""

    model_config = {"extra": "allow"}

    platform: str = Field(default="x", description="Source platform code")
    fetched_at_utc: str | None = Field(default=None, description="Batch crawl timestamp")
    max_posts_per_user: int = Field(default=3, ge=1, le=20, description="每账号入库帖子数")
    top_replies_per_post: int = Field(default=5, ge=0, le=20, description="每帖保留热门回复数")
    include_replies: bool = Field(default=True, description="是否抓取/保留回复信息")
    users: list[dict[str, Any]] = Field(default_factory=list)


class SocialIngestResponse(BaseModel):
    platform: str
    users: int
    kol_accounts_upserted: int
    accounts_upserted: int
    posts_upserted: int
    skipped_posts: int = 0
