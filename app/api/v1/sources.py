from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_article_search_params
from app.schemas.article import ArticleBrief, ArticleSearchParams
from app.schemas.common import ErrorResponse, PaginatedResponse
from app.schemas.crawl_log import CrawlLogResponse
from app.schemas.source import (
    ApiDeprecationResponse,
    SourceCatalogResponse,
    SourceFacetsResponse,
    SourceResolveResponse,
    SourceResponse,
    SourceUpdate,
)
from app.services import crawl_service, source_service

router = APIRouter()


@router.get(
    "",
    response_model=list[SourceResponse],
    summary="信源列表",
    description="查询所有信源及其状态信息，可按维度过滤。",
)
async def list_sources(
    dimension: str | None = Query(default=None, description="按单个维度过滤"),
    dimensions: str | None = Query(default=None, description="按多个维度过滤（逗号分隔）"),
    group: str | None = Query(default=None, description="按单个分组过滤"),
    groups: str | None = Query(default=None, description="按多个分组过滤（逗号分隔）"),
    tag: str | None = Query(default=None, description="按单个标签过滤"),
    tags: str | None = Query(default=None, description="按多个标签过滤（逗号分隔，OR 关系）"),
    crawl_method: str | None = Query(default=None, description="按爬取方式过滤"),
    source_type: str | None = Query(default=None, description="按信源类型过滤"),
    source_platform: str | None = Query(default=None, description="按信源平台过滤"),
    schedule: str | None = Query(default=None, description="按调度频率过滤"),
    taxonomy_domain: str | None = Query(default=None, description="按一级专业域过滤"),
    taxonomy_domains: str | None = Query(
        default=None, description="按多个一级专业域过滤（逗号分隔）"
    ),
    taxonomy_track: str | None = Query(default=None, description="按二级主题过滤"),
    taxonomy_tracks: str | None = Query(
        default=None, description="按多个二级主题过滤（逗号分隔）"
    ),
    taxonomy_scope: str | None = Query(default=None, description="按覆盖范围过滤"),
    taxonomy_scopes: str | None = Query(
        default=None, description="按多个覆盖范围过滤（逗号分隔）"
    ),
    is_enabled: bool | None = Query(default=None, description="按启用状态过滤"),
    health_status: str | None = Query(default=None, description="按健康状态过滤"),
    health_statuses: str | None = Query(
        default=None, description="按多个健康状态过滤（逗号分隔）"
    ),
    keyword: str | None = Query(default=None, description="关键词（匹配 ID/名称/分组/标签/URL）"),
    sort_by: str = Query(default="dimension_priority", description="排序字段"),
    order: str = Query(default="asc", description="排序方向: asc | desc"),
):
    return await source_service.list_sources(
        dimension,
        dimensions=dimensions,
        group=group,
        groups=groups,
        tag=tag,
        tags=tags,
        crawl_method=crawl_method,
        source_type=source_type,
        source_platform=source_platform,
        schedule=schedule,
        taxonomy_domain=taxonomy_domain,
        taxonomy_domains=taxonomy_domains,
        taxonomy_track=taxonomy_track,
        taxonomy_tracks=taxonomy_tracks,
        taxonomy_scope=taxonomy_scope,
        taxonomy_scopes=taxonomy_scopes,
        is_enabled=is_enabled,
        health_status=health_status,
        health_statuses=health_statuses,
        keyword=keyword,
        sort_by=sort_by,
        order=order,
    )


@router.get(
    "/catalog",
    response_model=SourceCatalogResponse,
    summary="信源目录（分页 + 分面）",
    description=(
        "信源全景目录接口。支持多维筛选、分页、排序，并返回分面聚合，适合前端/Agent 构建"
        "“按维度快速理解信源结构”的检索体验。"
    ),
)
async def list_sources_catalog(
    dimension: str | None = Query(default=None, description="按单个维度过滤"),
    dimensions: str | None = Query(default=None, description="按多个维度过滤（逗号分隔）"),
    group: str | None = Query(default=None, description="按单个分组过滤"),
    groups: str | None = Query(default=None, description="按多个分组过滤（逗号分隔）"),
    tag: str | None = Query(default=None, description="按单个标签过滤"),
    tags: str | None = Query(default=None, description="按多个标签过滤（逗号分隔，OR 关系）"),
    crawl_method: str | None = Query(default=None, description="按爬取方式过滤"),
    source_type: str | None = Query(default=None, description="按信源类型过滤"),
    source_platform: str | None = Query(default=None, description="按信源平台过滤"),
    schedule: str | None = Query(default=None, description="按调度频率过滤"),
    taxonomy_domain: str | None = Query(default=None, description="按一级专业域过滤"),
    taxonomy_domains: str | None = Query(
        default=None, description="按多个一级专业域过滤（逗号分隔）"
    ),
    taxonomy_track: str | None = Query(default=None, description="按二级主题过滤"),
    taxonomy_tracks: str | None = Query(
        default=None, description="按多个二级主题过滤（逗号分隔）"
    ),
    taxonomy_scope: str | None = Query(default=None, description="按覆盖范围过滤"),
    taxonomy_scopes: str | None = Query(
        default=None, description="按多个覆盖范围过滤（逗号分隔）"
    ),
    is_enabled: bool | None = Query(default=None, description="按启用状态过滤"),
    health_status: str | None = Query(default=None, description="按健康状态过滤"),
    health_statuses: str | None = Query(
        default=None, description="按多个健康状态过滤（逗号分隔）"
    ),
    keyword: str | None = Query(default=None, description="关键词（匹配 ID/名称/分组/标签/URL）"),
    sort_by: str = Query(default="dimension_priority", description="排序字段"),
    order: str = Query(default="asc", description="排序方向: asc | desc"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=100, ge=1, le=500, description="每页条数"),
    include_facets: bool = Query(default=True, description="是否返回分面统计"),
):
    return await source_service.list_sources_catalog(
        dimension,
        dimensions=dimensions,
        group=group,
        groups=groups,
        tag=tag,
        tags=tags,
        crawl_method=crawl_method,
        source_type=source_type,
        source_platform=source_platform,
        schedule=schedule,
        taxonomy_domain=taxonomy_domain,
        taxonomy_domains=taxonomy_domains,
        taxonomy_track=taxonomy_track,
        taxonomy_tracks=taxonomy_tracks,
        taxonomy_scope=taxonomy_scope,
        taxonomy_scopes=taxonomy_scopes,
        is_enabled=is_enabled,
        health_status=health_status,
        health_statuses=health_statuses,
        keyword=keyword,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
        include_facets=include_facets,
    )


@router.get(
    "/facets",
    response_model=SourceFacetsResponse,
    summary="信源筛选分面",
    description=(
        "返回当前筛选条件下的维度/分组/标签/爬取方式/频率/健康状态分布，"
        "并包含 taxonomy 一级域/二级主题/覆盖范围分布。"
    ),
)
async def get_source_facets(
    dimension: str | None = Query(default=None, description="按单个维度过滤"),
    dimensions: str | None = Query(default=None, description="按多个维度过滤（逗号分隔）"),
    group: str | None = Query(default=None, description="按单个分组过滤"),
    groups: str | None = Query(default=None, description="按多个分组过滤（逗号分隔）"),
    tag: str | None = Query(default=None, description="按单个标签过滤"),
    tags: str | None = Query(default=None, description="按多个标签过滤（逗号分隔，OR 关系）"),
    crawl_method: str | None = Query(default=None, description="按爬取方式过滤"),
    source_type: str | None = Query(default=None, description="按信源类型过滤"),
    source_platform: str | None = Query(default=None, description="按信源平台过滤"),
    schedule: str | None = Query(default=None, description="按调度频率过滤"),
    taxonomy_domain: str | None = Query(default=None, description="按一级专业域过滤"),
    taxonomy_domains: str | None = Query(
        default=None, description="按多个一级专业域过滤（逗号分隔）"
    ),
    taxonomy_track: str | None = Query(default=None, description="按二级主题过滤"),
    taxonomy_tracks: str | None = Query(
        default=None, description="按多个二级主题过滤（逗号分隔）"
    ),
    taxonomy_scope: str | None = Query(default=None, description="按覆盖范围过滤"),
    taxonomy_scopes: str | None = Query(
        default=None, description="按多个覆盖范围过滤（逗号分隔）"
    ),
    is_enabled: bool | None = Query(default=None, description="按启用状态过滤"),
    health_status: str | None = Query(default=None, description="按健康状态过滤"),
    health_statuses: str | None = Query(
        default=None, description="按多个健康状态过滤（逗号分隔）"
    ),
    keyword: str | None = Query(default=None, description="关键词（匹配 ID/名称/分组/标签/URL）"),
):
    return await source_service.list_source_facets(
        dimension,
        dimensions=dimensions,
        group=group,
        groups=groups,
        tag=tag,
        tags=tags,
        crawl_method=crawl_method,
        source_type=source_type,
        source_platform=source_platform,
        schedule=schedule,
        taxonomy_domain=taxonomy_domain,
        taxonomy_domains=taxonomy_domains,
        taxonomy_track=taxonomy_track,
        taxonomy_tracks=taxonomy_tracks,
        taxonomy_scope=taxonomy_scope,
        taxonomy_scopes=taxonomy_scopes,
        is_enabled=is_enabled,
        health_status=health_status,
        health_statuses=health_statuses,
        keyword=keyword,
    )


@router.get(
    "/items",
    response_model=PaginatedResponse[ArticleBrief],
    summary="按信源取数据（统一入口）",
    description=(
        "按 source_id/source_ids/source_name/source_names 查询信源数据。"
        "该接口复用文章统一视图，适合外部团队按渠道快速取数。"
    ),
    responses={400: {"model": ErrorResponse, "description": "缺少信源筛选参数"}},
)
async def list_source_items(
    params: ArticleSearchParams = Depends(get_article_search_params),
):
    try:
        return await source_service.list_source_items(params, require_source_filter=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/resolve",
    response_model=SourceResolveResponse,
    summary="信源解析与直连入口",
    description=(
        "用于外部团队快速定位信源 ID 与推荐调用路径。"
        "可通过 q 模糊检索或 source_id 精确定位。"
    ),
)
async def resolve_sources(
    q: str | None = Query(default=None, description="关键词（匹配信源 ID/名称/分组/标签）"),
    source_id: str | None = Query(default=None, description="精确信源 ID"),
    dimension: str | None = Query(default=None, description="按维度过滤"),
    taxonomy_domain: str | None = Query(default=None, description="按一级专业域过滤"),
    taxonomy_track: str | None = Query(default=None, description="按二级主题过滤"),
    taxonomy_scope: str | None = Query(default=None, description="按覆盖范围过滤"),
    group: str | None = Query(default=None, description="按分组过滤"),
    tag: str | None = Query(default=None, description="按标签过滤"),
    is_enabled: bool | None = Query(default=None, description="按启用状态过滤"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=200, description="每页条数"),
):
    return await source_service.resolve_sources(
        q=q,
        source_id=source_id,
        dimension=dimension,
        taxonomy_domain=taxonomy_domain,
        taxonomy_track=taxonomy_track,
        taxonomy_scope=taxonomy_scope,
        group=group,
        tag=tag,
        is_enabled=is_enabled,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/deprecations",
    response_model=ApiDeprecationResponse,
    summary="API 弃用迁移表",
    description="返回当前已标记弃用的 API 及替代路径与 Sunset 日期。",
)
async def list_api_deprecations():
    return source_service.list_api_deprecations()


@router.get(
    "/{source_id}/items",
    response_model=PaginatedResponse[ArticleBrief],
    summary="单个信源数据流",
    description="按路径 source_id 获取单个信源的数据流，支持关键词/日期/分页排序参数。",
    responses={404: {"model": ErrorResponse, "description": "信源不存在"}},
)
async def get_source_items(
    source_id: str,
    params: ArticleSearchParams = Depends(get_article_search_params),
):
    result = await source_service.list_source_items_for_source(source_id, params)
    if result is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return result


@router.get(
    "/{source_id}",
    response_model=SourceResponse,
    summary="信源详情",
    description="根据信源 ID 获取详细配置和运行状态。",
    responses={404: {"model": ErrorResponse, "description": "信源不存在"}},
)
async def get_source(
    source_id: str,
):
    source = await source_service.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.get(
    "/{source_id}/logs",
    response_model=list[CrawlLogResponse],
    summary="爬取日志",
    description="获取指定信源的最近爬取日志，默认返回最近 20 条。",
)
async def get_source_logs(
    source_id: str,
    limit: int = 20,
):
    return await crawl_service.get_crawl_logs(source_id=source_id, limit=limit)


@router.patch(
    "/{source_id}",
    response_model=SourceResponse,
    summary="启用/禁用信源",
    description="更新信源的启用状态。禁用后调度器将不再为该信源创建爬取任务。",
    responses={404: {"model": ErrorResponse, "description": "信源不存在"}},
)
async def update_source(
    source_id: str,
    data: SourceUpdate,
):
    source = await source_service.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if data.is_enabled is not None:
        return await source_service.update_source(source_id, data.is_enabled)
    return source


@router.post(
    "/{source_id}/trigger",
    summary="手动触发爬取",
    description="立即触发指定信源的一次爬取任务，不影响定时调度。",
    responses={
        404: {"model": ErrorResponse, "description": "信源不存在"},
        503: {"model": ErrorResponse, "description": "调度器未运行"},
    },
)
async def trigger_crawl(source_id: str):
    source = await source_service.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    from app.scheduler.manager import get_scheduler_manager

    manager = get_scheduler_manager()
    if manager is None:
        raise HTTPException(status_code=503, detail="Scheduler not running")
    await manager.trigger_source(source_id)
    return {"status": "triggered", "source_id": source_id}
