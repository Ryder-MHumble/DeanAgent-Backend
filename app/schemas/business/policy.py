"""Business schemas for Policy Intelligence module."""
from __future__ import annotations

from pydantic import BaseModel


class PolicyItem(BaseModel):
    """A policy article enriched with business metadata."""
    id: str
    title: str
    url: str
    agency: str = ""
    agency_type: str = "national"  # national | beijing | ministry
    match_score: int = 0  # 0-100, relevance to the institute
    funding: str | None = None
    deadline: str | None = None
    days_left: int | None = None
    status: str = "tracking"  # urgent | active | tracking
    published_at: str | None = None
    source_id: str = ""
    source_name: str = ""
    ai_insight: str = ""
    detail: str = ""


class PolicyListResponse(BaseModel):
    items: list[PolicyItem]
    total: int
    dimension: str
