from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.crawl_log import CrawlLogResponse
from app.schemas.source import SourceResponse, SourceUpdate
from app.services import crawl_service, source_service

router = APIRouter()


@router.get("/", response_model=list[SourceResponse])
async def list_sources(
    dimension: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """List all sources with status information."""
    return await source_service.list_sources(db, dimension)


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get a single source with details."""
    source = await source_service.get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.get("/{source_id}/logs", response_model=list[CrawlLogResponse])
async def get_source_logs(
    source_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db_session),
):
    """Get recent crawl logs for a source."""
    return await crawl_service.get_crawl_logs(db, source_id=source_id, limit=limit)


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: str,
    data: SourceUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Enable or disable a source."""
    source = await source_service.get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if data.is_enabled is not None:
        return await source_service.update_source(db, source_id, data.is_enabled)
    return source


@router.post("/{source_id}/trigger")
async def trigger_crawl(source_id: str, db: AsyncSession = Depends(get_db_session)):
    """Manually trigger a crawl for one source."""
    source = await source_service.get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    # Import here to avoid circular imports at module level
    from app.scheduler.manager import get_scheduler_manager

    manager = get_scheduler_manager()
    if manager is None:
        raise HTTPException(status_code=503, detail="Scheduler not running")
    await manager.trigger_source(source_id)
    return {"status": "triggered", "source_id": source_id}
