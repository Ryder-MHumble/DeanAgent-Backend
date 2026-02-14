from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.crawl_log import CrawlLog
from app.models.source import Source
from app.schemas.crawl_log import CrawlHealthResponse


async def get_crawl_logs(
    db: AsyncSession, source_id: str | None = None, limit: int = 50
) -> list[CrawlLog]:
    query = select(CrawlLog).order_by(CrawlLog.started_at.desc()).limit(limit)
    if source_id:
        query = query.where(CrawlLog.source_id == source_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_crawl_health(db: AsyncSession) -> CrawlHealthResponse:
    """Aggregate crawl health statistics."""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(hours=24)

    # Source counts
    total_sources = (await db.execute(select(func.count()).select_from(Source))).scalar() or 0
    enabled_sources = (
        await db.execute(
            select(func.count()).select_from(Source).where(Source.is_enabled.is_(True))
        )
    ).scalar() or 0

    # Health classification: healthy=0 failures, warning=1-2, failing=3+
    healthy = (
        await db.execute(
            select(func.count())
            .select_from(Source)
            .where(Source.is_enabled.is_(True), Source.consecutive_failures == 0)
        )
    ).scalar() or 0

    warning = (
        await db.execute(
            select(func.count())
            .select_from(Source)
            .where(
                Source.is_enabled.is_(True),
                Source.consecutive_failures > 0,
                Source.consecutive_failures <= 2,
            )
        )
    ).scalar() or 0

    failing = (
        await db.execute(
            select(func.count())
            .select_from(Source)
            .where(Source.is_enabled.is_(True), Source.consecutive_failures > 2)
        )
    ).scalar() or 0

    # Last 24h stats
    last_24h_crawls = (
        await db.execute(
            select(func.count())
            .select_from(CrawlLog)
            .where(CrawlLog.started_at >= yesterday)
        )
    ).scalar() or 0

    last_24h_articles = (
        await db.execute(
            select(func.count())
            .select_from(Article)
            .where(Article.crawled_at >= yesterday)
        )
    ).scalar() or 0

    return CrawlHealthResponse(
        total_sources=total_sources,
        enabled_sources=enabled_sources,
        healthy=healthy,
        warning=warning,
        failing=failing,
        last_24h_crawls=last_24h_crawls,
        last_24h_new_articles=last_24h_articles,
    )
