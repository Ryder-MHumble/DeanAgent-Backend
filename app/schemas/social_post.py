"""Schemas for social_posts table APIs."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SocialPostBrief(BaseModel):
    id: str = Field(description="内部帖子 ID，格式 social:<platform>:<external_post_id>")
    platform: str
    external_post_id: str
    source_id: str
    source_name: str
    author_username: str
    author_display_name: str | None = None
    post_type: str = "post"
    content_text: str | None = None
    post_url: str | None = None
    published_at: datetime | None = None
    crawled_at: datetime | None = None
    like_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    quote_count: int = 0
    view_count: int = 0
    bookmark_count: int = 0
    top_replies_count: int = 0


class SocialPostDetail(SocialPostBrief):
    top_replies: list[dict[str, Any]] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class SocialPostStats(BaseModel):
    group: str
    count: int
