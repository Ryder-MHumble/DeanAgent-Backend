"""Scholar Institutions API — /api/v1/institutions/scholars/

Endpoints:
  GET  /institutions/scholars/        机构列表（分页 + 多维过滤）
  GET  /institutions/scholars/stats   统计数据
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.institution import (
    InstitutionTreeResponse,
    ScholarInstitutionsListResponse,
    ScholarInstitutionsStatsResponse,
)
from app.services import institution_service as svc

router = APIRouter()


@router.get(
    "/tree",
    response_model=InstitutionTreeResponse,
    summary="机构分类树",
    description=(
        "返回按 group → category → institution 三层分类的机构树，供前端侧边栏使用。"
        "\n\n**分组（group）：** 共建高校 | 兄弟院校 | 海外高校 | 其他高校 | 科研院所 | 行业学会"
        "\n\n**分类（category）：** 示范性合作伙伴 | 京内高校 | 京外C9 | 综合强校 | 工科强校 | "
        "特色高校 | 香港高校 | 亚太高校 | 欧美高校 | 其他地区高校 | 特色专科学校 | 北京市属高校 | "
        "地方重点高校 | 科研院所-同行业 | 科研院所-交叉学科 | 科研院所-国家实验室 | 行业学会"
        "\n\n每个机构包含院系列表和学者数量。未设置 category 的机构归入对应顶层分组的空 category 桶。"
    ),
)
async def get_institution_tree():
    """返回机构分类树."""
    return await svc.get_institution_tree()


@router.get(
    "/",
    response_model=ScholarInstitutionsListResponse,
    summary="机构列表",
    description=(
        "获取所有高校及其院系，包含学者数量统计。"
        "支持按名称搜索、地区、机构类型过滤和分页。"
        "\n\n**地区（region）：** 国内 | 国际"
        "（根据机构名称自动推断：含中文字符默认国内，"
        "含 University/Institute 等英文关键词默认国际）"
        "\n\n**机构类型（affiliation_type）：** "
        "高校 | 企业 | 研究机构 | 其他"
        "（根据机构名称自动推断：含大学/学院为高校，"
        "含研究院/研究所为研究机构，含公司/集团为企业）"
    ),
)
async def list_scholar_institutions(
    keyword: str | None = Query(
        None, description="按高校名称搜索（模糊匹配）",
    ),
    region: str | None = Query(
        None, description="地区筛选：国内 | 国际",
    ),
    affiliation_type: str | None = Query(
        None,
        description="机构类型：高校 | 企业 | 研究机构 | 其他",
    ),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(
        20, ge=1, le=100, description="每页条数",
    ),
):
    return await svc.get_scholar_institutions_list(
        keyword=keyword,
        region=region,
        affiliation_type=affiliation_type,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/stats",
    response_model=ScholarInstitutionsStatsResponse,
    summary="统计数据",
    description=(
        "返回高校、院系、学者的总体统计信息。"
        "支持按地区和机构类型过滤。"
    ),
)
async def get_scholar_institutions_stats(
    region: str | None = Query(
        None, description="地区筛选：国内 | 国际",
    ),
    affiliation_type: str | None = Query(
        None,
        description="机构类型：高校 | 企业 | 研究机构 | 其他",
    ),
):
    return await svc.get_scholar_institutions_stats(
        region=region,
        affiliation_type=affiliation_type,
    )
