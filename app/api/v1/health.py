from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.crawl_log import CrawlHealthResponse
from app.services import crawl_service

router = APIRouter()


@router.get("/")
async def health_check(db: AsyncSession = Depends(get_db_session)):
    """Basic system health check."""
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


@router.get("/crawl-status", response_model=CrawlHealthResponse)
async def crawl_status(db: AsyncSession = Depends(get_db_session)):
    """Overview of crawl health across all sources."""
    return await crawl_service.get_crawl_health(db)
