"""Business schemas for Talent Radar module."""
from __future__ import annotations

from pydantic import BaseModel


class TalentEntry(BaseModel):
    """A talent/researcher entry."""
    id: str
    title: str
    url: str
    institution: str = ""
    source_id: str = ""
    source_name: str = ""
    date: str | None = None
    tags: list[str] = []
    ai_analysis: str = ""


class MobilityEvent(BaseModel):
    """An academic talent mobility event."""
    id: str
    talent_name: str = ""
    from_institution: str = ""
    to_institution: str = ""
    direction: str = ""
    impact: str = "medium"
    date: str | None = None
    event_type: str = ""  # inflow | outflow | external
    ai_analysis: str = ""
    detail: str = ""


class TalentListResponse(BaseModel):
    items: list[TalentEntry]
    total: int


class MobilityListResponse(BaseModel):
    items: list[MobilityEvent]
    total: int
