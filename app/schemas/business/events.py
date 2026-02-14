"""Business schemas for Events module."""
from __future__ import annotations

from pydantic import BaseModel


class RecommendedActivity(BaseModel):
    """A recommended activity/event."""
    id: str
    name: str
    url: str = ""
    date: str | None = None
    location: str = ""
    category: str = ""
    relevance_score: int = 0  # 0-100
    reason: str = ""
    detail: str = ""
    source_id: str = ""
    source_name: str = ""
    ai_explanation: str = ""
    highlights: list[str] = []


class EventListResponse(BaseModel):
    items: list[RecommendedActivity]
    total: int
