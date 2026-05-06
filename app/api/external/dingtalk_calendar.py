"""DingTalk calendar endpoints backed by dws CLI."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.schemas.dingtalk_calendar import (
    DingTalkCalendarEvent,
    DingTalkCalendarEventsResponse,
)
from app.services.external.dingtalk_calendar import (
    DingTalkCalendarService,
    DwsCalendarError,
)

router = APIRouter()
calendar_service = DingTalkCalendarService()


@router.get(
    "/events",
    response_model=DingTalkCalendarEventsResponse,
    summary="实时读取钉钉日程活动",
    description=(
        "通过 DingTalk Workspace CLI (`dws`) 实时读取当前登录账号可访问的日程活动。"
        "默认查询今天，并默认逐条拉取详情。"
    ),
)
async def list_calendar_events(
    start: datetime | None = Query(
        None,
        description="开始时间 ISO-8601；不传 start/end 时默认今天",
    ),
    end: datetime | None = Query(
        None,
        description="结束时间 ISO-8601；不传 start/end 时默认今天",
    ),
    include_details: bool = Query(
        True,
        description="是否对列表中的每个日程追加调用详情接口",
    ),
    max_detail_count: int = Query(
        50,
        ge=0,
        le=200,
        description="最多拉取详情的日程数，避免单次请求触发过多 CLI 调用",
    ),
):
    try:
        return await calendar_service.list_events(
            start=start,
            end=end,
            include_details=include_details,
            max_detail_count=max_detail_count,
        )
    except DwsCalendarError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get(
    "/events/{event_id}",
    response_model=DingTalkCalendarEvent,
    summary="实时读取钉钉日程详情",
    description="通过 `dws calendar event get --id` 获取单个日程的完整详情并归一化返回。",
)
async def get_calendar_event(event_id: str):
    try:
        return await calendar_service.get_event_detail(event_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DwsCalendarError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
