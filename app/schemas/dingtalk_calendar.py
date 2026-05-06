"""Pydantic schemas for DingTalk calendar API responses."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DingTalkCalendarEvent(BaseModel):
    """A normalized DingTalk calendar event with raw CLI data preserved."""

    event_id: str | None = Field(default=None, description="钉钉日程 ID")
    title: str | None = Field(default=None, description="日程标题")
    description: str | None = Field(default=None, description="日程描述/正文")
    start: str | dict[str, Any] | None = Field(default=None, description="原始开始时间字段")
    end: str | dict[str, Any] | None = Field(default=None, description="原始结束时间字段")
    start_time: str | None = Field(default=None, description="归一化开始时间")
    end_time: str | None = Field(default=None, description="归一化结束时间")
    timezone: str | None = Field(default=None, description="日程时区")
    location: str | None = Field(default=None, description="地点/会议室显示名")
    organizer: dict[str, Any] | None = Field(default=None, description="组织者原始对象")
    participants: list[dict[str, Any]] = Field(default_factory=list, description="参与者列表")
    rooms: list[dict[str, Any]] = Field(default_factory=list, description="会议室/资源列表")
    raw: dict[str, Any] = Field(default_factory=dict, description="dws 返回的原始事件对象")


class DingTalkCalendarEventsResponse(BaseModel):
    """Realtime DingTalk calendar event list response."""

    generated_at: str = Field(description="后端读取时间 (ISO 8601)")
    range_start: str | None = Field(default=None, description="查询开始时间")
    range_end: str | None = Field(default=None, description="查询结束时间")
    source: Literal["dws"] = Field(description="数据来源")
    count: int = Field(description="事件数量")
    events: list[DingTalkCalendarEvent] = Field(description="归一化日程列表")
