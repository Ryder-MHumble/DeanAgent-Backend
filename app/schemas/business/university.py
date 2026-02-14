"""Business schemas for University Ecosystem module."""
from __future__ import annotations

from pydantic import BaseModel


class PeerInstitution(BaseModel):
    """A peer institution's recent activity."""
    id: str
    name: str
    activity_level: int = 0  # number of recent items
    latest_action: str = ""
    action_type: str = ""
    threat_level: str = "normal"  # critical | warning | normal
    recent_count: int = 0
    ai_insight: str = ""
    detail: str = ""


class ResearchOutput(BaseModel):
    """A research output (paper, patent, award)."""
    id: str
    title: str
    institution: str = ""
    output_type: str = ""  # 论文 | 专利 | 获奖
    influence: str = "中"  # 高 | 中 | 低
    date: str | None = None
    field: str = ""
    authors: str = ""
    ai_analysis: str = ""
    detail: str = ""


class PersonnelChange(BaseModel):
    """A personnel change event."""
    id: str
    person: str = ""
    from_position: str = ""
    to_position: str = ""
    institution: str = ""
    change_type: str = ""  # 任命 | 离职 | 调动
    impact: str = "一般"  # 重大 | 较大 | 一般
    date: str | None = None
    background: str = ""
    ai_analysis: str = ""
    detail: str = ""
    # Raw article info
    title: str = ""
    url: str = ""
    source_id: str = ""


class PeerListResponse(BaseModel):
    items: list[PeerInstitution]
    total: int


class ResearchListResponse(BaseModel):
    items: list[ResearchOutput]
    total: int


class PersonnelListResponse(BaseModel):
    items: list[PersonnelChange]
    total: int
