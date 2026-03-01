"""Faculty API — /api/v1/faculty/

Endpoints:
  GET  /faculty/                         师资列表（分页 + 多维度筛选）
  GET  /faculty/stats                    统计数据
  GET  /faculty/sources                  信源列表
  GET  /faculty/{url_hash}               单条师资详情
  PATCH /faculty/{url_hash}/relation     更新「与两院关系」字段（用户管理）
  POST  /faculty/{url_hash}/updates      新增用户备注动态
  DELETE /faculty/{url_hash}/updates/{update_idx}  删除用户备注动态
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.faculty import (
    FacultyDetailResponse,
    FacultyListResponse,
    FacultySourcesResponse,
    FacultyStatsResponse,
    InstituteRelationUpdate,
    UserUpdateCreate,
)
from app.services import faculty_service as svc

router = APIRouter()


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=FacultyListResponse,
    summary="师资列表",
    description=(
        "获取 university_faculty 维度下的师资列表，支持按高校、院系、职称、"
        "学术称号、关键词、数据完整度及信源过滤，按姓名升序排列。"
    ),
)
async def list_faculty(
    university: str | None = Query(None, description="高校名称（模糊匹配）"),
    department: str | None = Query(None, description="院系名称（模糊匹配）"),
    group: str | None = Query(None, description="信源分组（精确匹配，如 sjtu/pku/cas）"),
    position: str | None = Query(
        None, description="职称（精确匹配，如 教授/副教授/研究员/助理教授）"
    ),
    is_academician: bool | None = Query(None, description="仅显示院士"),
    is_potential_recruit: bool | None = Query(None, description="仅显示潜在招募对象"),
    is_advisor_committee: bool | None = Query(None, description="仅显示顾问委员会成员"),
    has_email: bool | None = Query(None, description="仅显示有邮箱联系方式的师资"),
    min_completeness: int | None = Query(
        None, ge=0, le=100, description="数据完整度下限（0–100）"
    ),
    keyword: str | None = Query(
        None, description="关键词搜索（姓名/英文名/bio/研究方向/关键词）"
    ),
    source_id: str | None = Query(None, description="按单个信源 ID 筛选（精确匹配）"),
    source_ids: str | None = Query(
        None, description="按多个信源 ID 筛选（逗号分隔，精确匹配）"
    ),
    source_name: str | None = Query(None, description="按单个信源名称筛选（模糊匹配）"),
    source_names: str | None = Query(
        None, description="按多个信源名称筛选（逗号分隔，模糊匹配）"
    ),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
):
    return svc.get_faculty_list(
        university=university,
        department=department,
        group=group,
        position=position,
        is_academician=is_academician,
        is_potential_recruit=is_potential_recruit,
        is_advisor_committee=is_advisor_committee,
        has_email=has_email,
        min_completeness=min_completeness,
        keyword=keyword,
        source_id=source_id,
        source_ids=source_ids,
        source_name=source_name,
        source_names=source_names,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/stats",
    response_model=FacultyStatsResponse,
    summary="师资统计",
    description="返回师资库总览统计：总数、院士数、潜在招募数、按高校/职称分布、完整度分布。",
)
async def get_stats():
    return svc.get_faculty_stats()


@router.get(
    "/sources",
    response_model=FacultySourcesResponse,
    summary="师资信源列表",
    description="返回所有 university_faculty 维度的信源，含爬取状态和条目数。",
)
async def get_sources():
    return svc.get_faculty_sources()


@router.get(
    "/{url_hash}",
    response_model=FacultyDetailResponse,
    summary="师资详情",
    description="根据 url_hash 获取单条师资完整数据（爬虫字段 + 用户标注合并）。",
)
async def get_faculty(url_hash: str):
    result = svc.get_faculty_detail(url_hash)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Faculty '{url_hash}' not found")
    return result


# ---------------------------------------------------------------------------
# Write endpoints (user-managed fields only)
# ---------------------------------------------------------------------------


@router.patch(
    "/{url_hash}/relation",
    response_model=FacultyDetailResponse,
    summary="更新与两院关系",
    description=(
        "更新指定师资的「与两院关系」字段（顾问委员会、兼职导师、潜在招募等）。"
        "所有字段均可选，仅传入需要修改的字段。relation_updated_at 由服务端自动填写。"
        "这些字段永不被爬虫覆盖。"
    ),
)
async def update_relation(url_hash: str, body: InstituteRelationUpdate):
    updates = body.model_dump(exclude_none=True)
    result = svc.update_faculty_relation(url_hash, updates)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Faculty '{url_hash}' not found")
    return result


@router.post(
    "/{url_hash}/updates",
    response_model=FacultyDetailResponse,
    summary="新增用户备注动态",
    description=(
        "为指定师资新增一条用户录入的动态备注（获奖/项目立项/任职履新等）。"
        "added_by 自动转换为 'user:{added_by}'，created_at 由服务端自动填写。"
    ),
    status_code=201,
)
async def add_update(url_hash: str, body: UserUpdateCreate):
    result = svc.add_faculty_update(url_hash, body.model_dump())
    if result is None:
        raise HTTPException(status_code=404, detail=f"Faculty '{url_hash}' not found")
    return result


@router.delete(
    "/{url_hash}/updates/{update_idx}",
    response_model=FacultyDetailResponse,
    summary="删除用户备注动态",
    description=(
        "删除指定师资的用户备注动态（按 user_updates 列表中的索引）。"
        "只能删除 added_by 以 'user:' 开头的条目；尝试删除爬虫动态将返回 403。"
    ),
)
async def delete_update(url_hash: str, update_idx: int):
    try:
        result = svc.delete_faculty_update(url_hash, update_idx)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail=f"Faculty '{url_hash}' not found")
    return result
