from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.crawl_log import CrawlHealthResponse
from app.services import crawl_service

router = APIRouter()


@router.get(
    "/",
    summary="系统健康检查",
    description="检查数据库连接和调度器运行状态，用于监控和部署健康探针。",
)
async def health_check():
    from app.scheduler.manager import get_scheduler_manager

    scheduler = get_scheduler_manager()
    scheduler_status = "running" if scheduler else "not_started"

    # Try DB connection (non-blocking)
    db_status = "not_configured"
    if scheduler and scheduler.db_available:
        try:
            from sqlalchemy import text

            from app.database import async_session_factory

            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {e}"

    return {
        "status": "ok",
        "database": db_status,
        "scheduler": scheduler_status,
    }


@router.get(
    "/crawl-status",
    response_model=CrawlHealthResponse,
    summary="爬取健康概览",
    description="获取全局爬取健康度统计，包括健康/告警/失败的信源数和近 24 小时活跃度。",
)
async def crawl_status(db: AsyncSession = Depends(get_db)):
    return await crawl_service.get_crawl_health(db)


@router.get(
    "/pipeline-status",
    summary="管线状态",
    description="获取上次每日管线运行的状态、各阶段耗时和结果摘要。",
)
async def pipeline_status():
    from app.scheduler.pipeline import get_last_pipeline_result

    result = get_last_pipeline_result()
    if result is None:
        return {"status": "never_run", "message": "Pipeline has not run yet"}
    return result.to_dict()


@router.post(
    "/pipeline-trigger",
    summary="手动触发管线",
    description="手动触发每日管线：全量爬取 → 政策处理 → 人事处理。",
)
async def trigger_pipeline():
    from app.scheduler.manager import get_scheduler_manager

    mgr = get_scheduler_manager()
    if mgr is None:
        raise HTTPException(503, "Scheduler not running")
    await mgr.trigger_pipeline()
    return {"status": "triggered", "message": "Daily pipeline triggered"}
