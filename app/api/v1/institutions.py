"""Institution API — /api/v1/institutions/

Endpoints:
  GET    /institutions/           机构列表（分页 + 筛选）
  GET    /institutions/stats      统计数据
  GET    /institutions/{id}       机构详情
  POST   /institutions/           创建机构
  PATCH  /institutions/{id}       更新机构
  DELETE /institutions/{id}       删除机构
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.institution import (
    InstitutionCreate,
    InstitutionDetailResponse,
    InstitutionListResponse,
    InstitutionStatsResponse,
    InstitutionUpdate,
)
from app.services import institution_service as svc

router = APIRouter()


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=InstitutionListResponse,
    summary="机构列表",
    description="获取机构列表，支持按分类、优先级、关键词筛选，按优先级和名称排序。",
)
async def list_institutions(
    category: str | None = Query(None, description="分类筛选（精确匹配）"),
    priority: str | None = Query(None, description="优先级筛选（P0/P1/P2/P3）"),
    keyword: str | None = Query(None, description="关键词搜索（名称/院系）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
):
    return svc.get_institution_list(
        category=category,
        priority=priority,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/stats",
    response_model=InstitutionStatsResponse,
    summary="机构统计",
    description="返回机构总览统计：总数、示范校数、按分类/优先级/合作重点分布、学生导师总数。",
)
async def get_stats():
    return svc.get_institution_stats()


@router.get(
    "/{institution_id}",
    response_model=InstitutionDetailResponse,
    summary="机构详情",
    description="根据机构 ID 获取完整机构信息（基本信息、人员、合作、交流记录）。",
)
async def get_institution(institution_id: str):
    result = svc.get_institution_detail(institution_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Institution '{institution_id}' not found"
        )
    return result


# ---------------------------------------------------------------------------
# Write endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=InstitutionDetailResponse,
    summary="创建机构",
    description="创建新的机构记录。ID 必须唯一，不能与现有机构重复。",
    status_code=201,
)
async def create_institution(body: InstitutionCreate):
    try:
        return svc.create_institution(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/{institution_id}",
    response_model=InstitutionDetailResponse,
    summary="更新机构",
    description="更新指定机构的信息。所有字段均可选，仅传入需要修改的字段。",
)
async def update_institution(institution_id: str, body: InstitutionUpdate):
    updates = body.model_dump(exclude_none=True)
    result = svc.update_institution(institution_id, updates)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Institution '{institution_id}' not found"
        )
    return result


@router.delete(
    "/{institution_id}",
    summary="删除机构",
    description="删除指定的机构记录。",
    status_code=204,
)
async def delete_institution(institution_id: str):
    deleted = svc.delete_institution(institution_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Institution '{institution_id}' not found"
        )
