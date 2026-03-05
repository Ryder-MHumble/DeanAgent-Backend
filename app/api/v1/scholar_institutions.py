"""Scholar Institutions API — /api/v1/institutions/scholars/

Endpoints:
  GET  /institutions/scholars/        机构列表（分页 + 关键词搜索）
  GET  /institutions/scholars/stats   统计数据
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.institution import (
    ScholarInstitutionsListResponse,
    ScholarInstitutionsStatsResponse,
)
from app.services import institution_service as svc

router = APIRouter()


@router.get(
    "/",
    response_model=ScholarInstitutionsListResponse,
    summary="机构列表",
    description="获取所有高校及其院系，包含学者数量统计。支持按名称搜索和分页。",
)
async def list_scholar_institutions(
    keyword: str | None = Query(None, description="按高校名称搜索（模糊匹配）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    return svc.get_scholar_institutions_list(
        keyword=keyword,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/stats",
    response_model=ScholarInstitutionsStatsResponse,
    summary="统计数据",
    description="返回高校、院系、学者的总体统计信息。",
)
async def get_scholar_institutions_stats():
    return svc.get_scholar_institutions_stats()
