from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.schemas.common import ErrorResponse
from app.schemas.console import (
    CrawlJobResponse,
    CrawlRequest,
    CrawlStartResponse,
    CrawlStatusResponse,
    ConsoleApiUsageResponse,
    ConsoleDailyTrendPoint,
    ConsoleOverviewResponse,
    ConsoleServerMetrics,
    ConsoleSourceLogsResponse,
)
from app.schemas.source import SourceCatalogResponse, SourceResponse, SourceUpdate
from app.services import console_service, source_service
from app.services.crawler_control_service import (
    CrawlJobNotFoundError,
    CrawlJobStateError,
    CrawlJobValidationError,
    get_control_service,
)

router = APIRouter()


def _map_job_error(exc: Exception) -> HTTPException:
    if isinstance(exc, CrawlJobNotFoundError):
        return HTTPException(status_code=404, detail="Job not found")
    if isinstance(exc, CrawlJobStateError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, CrawlJobValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


def _to_legacy_start_response(job: dict) -> CrawlStartResponse:
    return CrawlStartResponse(
        status="started",
        requested_source_count=job["requested_source_count"],
        accepted_source_count=job["accepted_source_count"],
        rejected_source_ids=job["rejected_source_ids"],
    )


@router.get(
    "/overview",
    response_model=ConsoleOverviewResponse,
    tags=["console-overview"],
    summary="控制台总览",
    description="返回控制台首页所需的核心总览：系统健康、今日汇总、维度分布、最近运行记录与手动任务状态。",
)
async def get_overview():
    return await console_service.get_console_overview()


@router.get(
    "/daily-trend",
    response_model=list[ConsoleDailyTrendPoint],
    tags=["console-overview"],
    summary="每日爬取趋势",
    description="返回最近 N 天的爬取次数、成功/失败分布及条目量，供前端绘制趋势图。",
)
async def get_daily_trend(
    days: int = Query(default=7, ge=1, le=30, description="返回最近天数"),
):
    return await console_service.get_console_daily_trend(days=days)


@router.get(
    "/server-metrics",
    response_model=ConsoleServerMetrics,
    tags=["console-overview"],
    summary="服务器运行指标",
    description="返回控制台顶部运维概览所需的 CPU、内存、磁盘、负载和运行时长。",
)
async def get_server_metrics():
    return await console_service.get_console_server_metrics()




@router.get(
    "/api-monitor/usage",
    response_model=ConsoleApiUsageResponse,
    tags=["console-overview"],
    summary="API token/费用监控",
    description="返回 OpenRouter API 的 token 消耗、费用、模块归因与最近调用明细；未知模型按 unpriced 返回并单独统计。",
)
async def get_api_usage(
    days: int = Query(default=7, ge=1, le=30, description="统计最近天数"),
    system: str | None = Query(default=None, description="按系统过滤"),
    module: str | None = Query(default=None, description="按模块过滤"),
    stage: str | None = Query(default=None, description="按 stage 过滤"),
    model: str | None = Query(default=None, description="按模型过滤"),
    source_id: str | None = Query(default=None, description="按 source_id 过滤"),
    success: str = Query(default="all", description="调用状态过滤：all/success/failed"),
    limit: int = Query(default=80, ge=1, le=200, description="最近明细条数"),
):
    return await console_service.get_console_api_usage(
        days=days,
        system=system,
        module=module,
        stage=stage,
        model=model,
        source_id=source_id,
        success=success,
        limit=limit,
    )

@router.get(
    "/sources",
    response_model=SourceCatalogResponse,
    tags=["console-sources"],
    summary="控制台信源列表",
    description="控制台专用信源目录接口，复用统一信源目录能力，但挂在独立 console-api 下。",
)
async def list_console_sources(
    dimension: str | None = Query(default=None, description="按单个维度过滤"),
    dimensions: str | None = Query(default=None, description="按多个维度过滤（逗号分隔）"),
    group: str | None = Query(default=None, description="按单个分组过滤"),
    groups: str | None = Query(default=None, description="按多个分组过滤（逗号分隔）"),
    tag: str | None = Query(default=None, description="按单个标签过滤"),
    tags: str | None = Query(default=None, description="按多个标签过滤（逗号分隔）"),
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
    order: str = Query(default="asc", description="排序方向"),
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
    "/sources/{source_id}/logs",
    response_model=ConsoleSourceLogsResponse,
    tags=["console-sources"],
    summary="信源最近日志",
    responses={404: {"model": ErrorResponse, "description": "信源不存在"}},
)
async def get_console_source_logs(
    source_id: str,
    limit: int = Query(default=20, ge=1, le=200, description="最近日志条数"),
):
    try:
        return await console_service.get_console_source_logs(source_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch(
    "/sources/{source_id}",
    response_model=SourceResponse,
    tags=["console-sources"],
    summary="启用或禁用信源",
    responses={404: {"model": ErrorResponse, "description": "信源不存在"}},
)
async def update_console_source(source_id: str, data: SourceUpdate):
    source = await source_service.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if data.is_enabled is not None:
        return await source_service.update_source(source_id, data.is_enabled)
    return source


@router.post(
    "/sources/{source_id}/trigger",
    tags=["console-sources"],
    summary="手动触发单个信源",
    responses={
        404: {"model": ErrorResponse, "description": "信源不存在"},
        503: {"model": ErrorResponse, "description": "调度器未运行"},
    },
)
async def trigger_console_source(source_id: str):
    source = await source_service.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    from app.scheduler.manager import get_scheduler_manager

    manager = get_scheduler_manager()
    if manager is None:
        raise HTTPException(status_code=503, detail="Scheduler not running")
    await manager.trigger_source(source_id)
    return {"status": "triggered", "source_id": source_id}


@router.post(
    "/jobs",
    response_model=CrawlJobResponse,
    tags=["console-manual-jobs"],
    summary="创建手动批量爬取任务",
    responses={
        400: {"model": ErrorResponse, "description": "参数非法"},
        409: {"model": ErrorResponse, "description": "已有任务在运行"},
    },
)
async def create_manual_job(request: CrawlRequest):
    service = get_control_service()
    try:
        return service.create_job(
            source_ids=request.source_ids,
            keyword_filter=request.keyword_filter,
            keyword_blacklist=request.keyword_blacklist,
            export_format=request.export_format,
        )
    except Exception as exc:  # noqa: BLE001
        raise _map_job_error(exc) from exc


@router.get(
    "/jobs/{job_id}",
    response_model=CrawlJobResponse,
    tags=["console-manual-jobs"],
    summary="查询手动任务状态",
    responses={404: {"model": ErrorResponse, "description": "任务不存在"}},
)
async def get_manual_job(job_id: str):
    service = get_control_service()
    try:
        return service.get_job(job_id)
    except Exception as exc:  # noqa: BLE001
        raise _map_job_error(exc) from exc


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=CrawlJobResponse,
    tags=["console-manual-jobs"],
    summary="取消手动任务",
    responses={
        404: {"model": ErrorResponse, "description": "任务不存在"},
        409: {"model": ErrorResponse, "description": "当前状态不允许取消"},
    },
)
async def cancel_manual_job(job_id: str):
    service = get_control_service()
    try:
        return service.cancel_job(job_id)
    except Exception as exc:  # noqa: BLE001
        raise _map_job_error(exc) from exc


@router.get(
    "/jobs/{job_id}/result",
    tags=["console-manual-jobs"],
    summary="下载指定手动任务结果",
    responses={404: {"model": ErrorResponse, "description": "任务不存在或结果文件不可用"}},
)
async def download_job_result(job_id: str):
    service = get_control_service()
    try:
        file_path = service.get_job_result_file(job_id)
    except Exception as exc:  # noqa: BLE001
        raise _map_job_error(exc) from exc

    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail="No result file available for this job")
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.post(
    "/manual-jobs/start",
    response_model=CrawlStartResponse,
    tags=["console-manual-jobs"],
    summary="启动手动批量爬取任务",
    deprecated=True,
    responses={400: {"model": ErrorResponse, "description": "参数非法或已有任务在运行"}},
)
async def start_manual_job(request: CrawlRequest):
    service = get_control_service()
    try:
        job = service.create_job(
            source_ids=request.source_ids,
            keyword_filter=request.keyword_filter,
            keyword_blacklist=request.keyword_blacklist,
            export_format=request.export_format,
        )
    except (CrawlJobStateError, CrawlJobValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_legacy_start_response(job)


@router.post(
    "/manual-jobs/stop",
    tags=["console-manual-jobs"],
    summary="停止手动任务",
    deprecated=True,
    responses={400: {"model": ErrorResponse, "description": "没有任务在运行"}},
)
async def stop_manual_job():
    service = get_control_service()
    if not service.is_running():
        raise HTTPException(status_code=400, detail="No crawl job is running")
    service.stop_crawl()
    return {"status": "stopped"}


@router.get(
    "/manual-jobs/status",
    response_model=CrawlStatusResponse,
    tags=["console-manual-jobs"],
    summary="手动任务状态",
    deprecated=True,
)
async def get_manual_job_status():
    return get_control_service().get_status()


@router.get(
    "/manual-jobs/download",
    tags=["console-manual-jobs"],
    summary="下载最近一次手动任务结果",
    deprecated=True,
    responses={404: {"model": ErrorResponse, "description": "没有可下载文件"}},
)
async def download_manual_job_result():
    file_path = get_control_service().get_result_file()
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail="No result file available")
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )
