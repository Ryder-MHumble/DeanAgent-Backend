"""Business schemas for Tech Frontier module."""
from __future__ import annotations

from pydantic import BaseModel


class IndustryNewsItem(BaseModel):
    """An industry news article with classification."""
    id: str
    title: str
    url: str
    source: str = ""
    news_type: str = ""  # 投融资 | 新产品 | 政策 | 收购 | 其他
    date: str | None = None
    impact: str = "一般"  # 重大 | 较大 | 一般
    summary: str = ""
    ai_analysis: str = ""
    relevance: str = ""


class TechTrend(BaseModel):
    """A technology trend item."""
    id: str
    topic: str
    heat_trend: str = "stable"  # surging | rising | stable | declining
    heat_label: str = ""
    our_status: str = "none"  # deployed | weak | none
    our_status_label: str = ""
    gap_level: str = "medium"  # high | medium | low
    key_metric: str = ""
    ai_insight: str = ""
    detail: str = ""


class HotTopic(BaseModel):
    """A hot topic from tech communities."""
    id: str
    title: str
    heat: int = 0
    max_heat: int = 100
    discussions: int = 0
    trend: str = "stable"  # up | stable | new
    tags: list[str] = []
    summary: str = ""
    ai_analysis: str = ""


class IndustryNewsResponse(BaseModel):
    items: list[IndustryNewsItem]
    total: int


class TechTrendResponse(BaseModel):
    items: list[TechTrend]
    total: int


class HotTopicResponse(BaseModel):
    items: list[HotTopic]
    total: int
