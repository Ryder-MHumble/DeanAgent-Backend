"""Event API — /api/v1/events/

Endpoints:
  GET    /events/                     活动列表（分页 + 筛选）
  GET    /events/stats                统计数据
  GET    /events/{id}                 活动详情
  POST   /events/                     创建活动
  PATCH  /events/{id}                 更新活动
  DELETE /events/{id}                 删除活动
  GET    /events/{id}/scholars        获取关联学者列表
  POST   /events/{id}/scholars        添加学者关联
  DELETE /events/{id}/scholars/{scholar_id}  移除学者关联
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.event import (
    EventCreate,
    EventDetailResponse,
    EventListResponse,
    EventStatsResponse,
    EventUpdate,
    ScholarAssociation,
)
from app.services import event_service as svc

router = APIRouter()


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=EventListResponse,
    summary="活动列表",
    description="获取活动列表，支持按类型、讲者、日期范围、关联学者、关键词筛选，按日期倒序排列。",
)
async def list_events(
    event_type: str | None = Query(None, description="活动类型筛选（精确匹配）"),
    speaker_name: str | None = Query(None, description="讲者姓名搜索（模糊匹配）"),
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    scholar_id: str | None = Query(None, description="按关联学者筛选"),
    keyword: str | None = Query(None, description="关键词搜索（标题/摘要/讲者）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
):
    return await svc.get_event_list(
        event_type=event_type,
        speaker_name=speaker_name,
        start_date=start_date,
        end_date=end_date,
        scholar_id=scholar_id,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/stats",
    response_model=EventStatsResponse,
    summary="活动统计",
    description="返回活动总览统计：总数、按类型/月份分布、总讲者数、平均时长。",
)
async def get_stats():
    return await svc.get_event_stats()


@router.get(
    "/{event_id}",
    response_model=EventDetailResponse,
    summary="活动详情",
    description="根据活动 ID 获取完整活动信息（讲者、时间、地点、关联学者等）。",
)
async def get_event(event_id: str):
    result = await svc.get_event_detail(event_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Write endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=EventDetailResponse,
    summary="创建活动",
    description="创建新的活动记录。ID 自动生成（UUID）。",
    status_code=201,
)
async def create_event(body: EventCreate):
    return await svc.create_event(body.model_dump())


@router.patch(
    "/{event_id}",
    response_model=EventDetailResponse,
    summary="更新活动",
    description="更新指定活动的信息。所有字段均可选，仅传入需要修改的字段。",
)
async def update_event(event_id: str, body: EventUpdate):
    updates = body.model_dump(exclude_none=True)
    result = await svc.update_event(event_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return result


@router.delete(
    "/{event_id}",
    summary="删除活动",
    description="删除指定的活动记录。",
    status_code=204,
)
async def delete_event(event_id: str):
    deleted = await svc.delete_event(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")


# ---------------------------------------------------------------------------
# Scholar association endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{event_id}/scholars",
    response_model=list[str],
    summary="获取活动关联的学者列表",
    description="返回指定活动关联的所有学者 url_hash 列表。",
)
async def get_event_scholars(event_id: str):
    result = await svc.get_event_scholars(event_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return result


@router.post(
    "/{event_id}/scholars",
    response_model=EventDetailResponse,
    summary="添加学者关联",
    description="为指定活动添加学者关联。如果学者已关联则不重复添加。",
    status_code=201,
)
async def add_scholar_to_event(event_id: str, body: ScholarAssociation):
    result = await svc.add_scholar_to_event(event_id, body.scholar_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return result


@router.delete(
    "/{event_id}/scholars/{scholar_id}",
    response_model=EventDetailResponse,
    summary="移除学者关联",
    description="移除指定活动与学者的关联关系。",
)
async def remove_scholar_from_event(event_id: str, scholar_id: str):
    result = await svc.remove_scholar_from_event(event_id, scholar_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return result
