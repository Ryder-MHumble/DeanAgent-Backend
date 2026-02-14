"""Business schemas for KOL (Key Opinion Leader) tracking."""
from __future__ import annotations

from pydantic import BaseModel


class KOLProfile(BaseModel):
    """A KOL profile with activity summary."""
    id: str
    name: str
    username: str
    affiliation: str = ""
    field: str = "AI"
    followers: int = 0
    influence: str = "高"  # 极高 | 高 | 中
    profile_pic: str = ""
    recent_activity: str = ""
    summary: str = ""
    ai_analysis: str = ""


class KOLTweet(BaseModel):
    """A tweet from a KOL."""
    id: str
    text: str
    url: str
    author_name: str
    author_username: str
    author_followers: int = 0
    created_at: str | None = None
    like_count: int = 0
    retweet_count: int = 0
    view_count: int = 0
    lang: str = ""


class KOLListResponse(BaseModel):
    profiles: list[KOLProfile]
    total: int


class KOLTweetsResponse(BaseModel):
    tweets: list[KOLTweet]
    total: int
    source: str = "twitter"
