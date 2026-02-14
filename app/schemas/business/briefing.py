"""Business schemas for Home Briefing module."""
from __future__ import annotations

from pydantic import BaseModel


class MetricCard(BaseModel):
    """A summary metric card for the dashboard."""
    dimension: str
    dimension_label: str
    total_items: int = 0
    source_count: int = 0
    latest_crawl: str | None = None


class PriorityItem(BaseModel):
    """A priority item for the daily briefing."""
    id: str
    title: str
    url: str = ""
    dimension: str = ""
    source_id: str = ""
    category: str = ""  # risk | deadline | opportunity
    score: float = 0.0
    description: str = ""
    ai_insight: str = ""


class DailySummary(BaseModel):
    """AI-generated daily summary."""
    summary: str
    generated_at: str
    dimensions_covered: list[str] = []
    total_articles_analyzed: int = 0


class MetricsResponse(BaseModel):
    cards: list[MetricCard]
    total_dimensions: int


class PriorityResponse(BaseModel):
    items: list[PriorityItem]
    total: int


class DailySummaryResponse(BaseModel):
    summary: DailySummary
