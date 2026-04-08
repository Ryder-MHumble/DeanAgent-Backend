"""Crawler control API for frontend UI."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.schemas.common import ErrorResponse
from app.schemas.console import (
    CrawlJobResponse,
    CrawlRequest,
    CrawlStartResponse,
    CrawlStatusResponse,
)
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


@router.post(
    "/jobs",
    response_model=CrawlJobResponse,
    summary="创建手动爬取任务",
    description="创建并立即启动一个新的手动爬取任务，返回 job_id 与初始状态。",
    responses={
        400: {"model": ErrorResponse, "description": "参数非法"},
        409: {"model": ErrorResponse, "description": "已有任务在运行"},
    },
)
async def create_crawl_job(request: CrawlRequest):
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
    summary="查询手动爬取任务状态",
    responses={404: {"model": ErrorResponse, "description": "任务不存在"}},
)
async def get_crawl_job(job_id: str):
    service = get_control_service()
    try:
        return service.get_job(job_id)
    except Exception as exc:  # noqa: BLE001
        raise _map_job_error(exc) from exc


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=CrawlJobResponse,
    summary="取消手动爬取任务",
    responses={
        404: {"model": ErrorResponse, "description": "任务不存在"},
        409: {"model": ErrorResponse, "description": "当前状态不允许取消"},
    },
)
async def cancel_crawl_job(job_id: str):
    service = get_control_service()
    try:
        return service.cancel_job(job_id)
    except Exception as exc:  # noqa: BLE001
        raise _map_job_error(exc) from exc


@router.get(
    "/jobs/{job_id}/result",
    summary="下载指定手动爬取任务结果",
    responses={
        404: {"model": ErrorResponse, "description": "任务不存在或结果文件不可用"},
    },
)
async def download_crawl_job_result(job_id: str):
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
    "/start",
    response_model=CrawlStartResponse,
    summary="启动爬取任务",
    description="兼容旧接口：内部转为创建新的 jobs 任务。",
    deprecated=True,
    responses={
        400: {"model": ErrorResponse, "description": "参数非法或已有任务在运行"},
    },
)
async def start_crawl(request: CrawlRequest):
    """Start a new crawl job via compatibility endpoint."""
    service = get_control_service()
    try:
        job = service.create_job(
            source_ids=request.source_ids,
            keyword_filter=request.keyword_filter,
            keyword_blacklist=request.keyword_blacklist,
            export_format=request.export_format,
        )
    except CrawlJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except (CrawlJobStateError, CrawlJobValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_legacy_start_response(job)


@router.post(
    "/stop",
    summary="停止爬取任务",
    description="兼容旧接口：内部转为取消当前运行中的最新任务。",
    deprecated=True,
    responses={
        400: {"model": ErrorResponse, "description": "没有任务在运行"},
    },
)
async def stop_crawl():
    """Stop the current crawl job."""
    service = get_control_service()

    if not service.is_running():
        raise HTTPException(status_code=400, detail="No crawl job is running")

    service.stop_crawl()
    return {"status": "stopped"}


@router.get(
    "/status",
    response_model=CrawlStatusResponse,
    summary="获取爬取状态",
    description="兼容旧接口：返回 latest job 的实时状态。",
    deprecated=True,
)
async def get_status():
    """Get current crawl job status."""
    service = get_control_service()
    return service.get_status()


@router.get(
    "/download",
    summary="下载爬取结果",
    description="兼容旧接口：下载 latest job 的结果文件。",
    deprecated=True,
    responses={
        404: {"model": ErrorResponse, "description": "没有可下载的文件"},
    },
)
async def download_result():
    """Download the latest crawl result file."""
    service = get_control_service()
    file_path = service.get_result_file()

    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail="No result file available")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )
