"""Pydantic schemas for Policy Intelligence API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class PolicyFeedItem(BaseModel):
    """Single item in the policy intelligence feed."""

    id: str
    title: str
    summary: str
    category: Literal["国家政策", "北京政策", "领导讲话", "政策机会"]
    importance: Literal["紧急", "重要", "关注", "一般"]
    date: str
    source: str
    tags: list[str] = []
    matchScore: int | None = None
    funding: str | None = None
    daysLeft: int | None = None
    leader: str | None = None
    relevance: int | None = None
    signals: list[str] | None = None
    sourceUrl: str | None = None
    aiInsight: str | None = None
    detail: str | None = None
    content: str | None = None


class PolicyItem(BaseModel):
    """Policy opportunity item for the intelligence table."""

    id: str
    name: str
    agency: str
    agencyType: Literal["national", "beijing", "ministry"]
    matchScore: int
    funding: str
    deadline: str
    daysLeft: int
    status: Literal["urgent", "active", "tracking"]
    aiInsight: str
    detail: str
    sourceUrl: str | None = None


class PolicyFeedResponse(BaseModel):
    """Response wrapper for the policy feed endpoint."""

    generated_at: str | None = None
    item_count: int
    items: list[PolicyFeedItem]


class PolicyOpportunitiesResponse(BaseModel):
    """Response wrapper for the policy opportunities endpoint."""

    generated_at: str | None = None
    item_count: int
    items: list[PolicyItem]
