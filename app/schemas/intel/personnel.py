"""Pydantic schemas for Personnel Intelligence API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class PersonnelChange(BaseModel):
    """A single personnel appointment or dismissal."""

    name: str
    action: Literal["任命", "免去"]
    position: str
    department: str | None = None
    date: str
    source_article_id: str


class PersonnelFeedItem(BaseModel):
    """Single item in the personnel intelligence feed."""

    id: str
    title: str
    date: str
    source: str
    importance: Literal["紧急", "重要", "关注", "一般"]
    matchScore: int
    changes: list[PersonnelChange] = []
    sourceUrl: str | None = None


class PersonnelFeedResponse(BaseModel):
    """Response wrapper for the personnel feed endpoint."""

    generated_at: str | None = None
    item_count: int
    items: list[PersonnelFeedItem]


class PersonnelChangesResponse(BaseModel):
    """Response wrapper for the personnel changes endpoint."""

    generated_at: str | None = None
    item_count: int
    items: list[PersonnelChange]


# ---------------------------------------------------------------------------
# Enriched personnel schemas (with LLM-generated fields)
# ---------------------------------------------------------------------------


class PersonnelChangeEnriched(BaseModel):
    """A single personnel change or article-level news item enriched with LLM analysis."""

    id: str
    name: str
    action: Literal["任命", "免去", "动态"]
    position: str
    department: str | None = None
    date: str
    source: str
    sourceUrl: str | None = None
    # LLM enriched fields
    relevance: int = 0
    importance: Literal["紧急", "重要", "关注", "一般"] = "一般"
    group: Literal["action", "watch"] = "watch"
    note: str | None = None
    actionSuggestion: str | None = None
    background: str | None = None
    signals: list[str] = []
    aiInsight: str | None = None


class PersonnelEnrichedFeedResponse(BaseModel):
    """Response wrapper for the enriched personnel feed."""

    generated_at: str | None = None
    total_count: int
    action_count: int = 0
    watch_count: int = 0
    items: list[PersonnelChangeEnriched]


class PersonnelEnrichedStatsResponse(BaseModel):
    """Statistics for enriched personnel data."""

    total_changes: int
    action_count: int
    watch_count: int
    by_department: dict[str, int] = {}
    by_action: dict[str, int] = {}
    high_relevance_count: int = 0
    generated_at: str | None = None
