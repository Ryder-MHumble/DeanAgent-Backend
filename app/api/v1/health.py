from fastapi import APIRouter, Depends
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
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        # Verify DB connection
        from sqlalchemy import text

        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    from app.scheduler.manager import get_scheduler_manager

    scheduler = get_scheduler_manager()
    scheduler_status = "running" if scheduler else "not_started"

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
