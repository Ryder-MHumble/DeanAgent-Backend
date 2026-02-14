from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.crawlers.base import CrawlResult, CrawlStatus
from app.crawlers.registry import CrawlerRegistry
from app.crawlers.utils.dedup import compute_url_hash
from app.crawlers.utils.json_storage import save_crawl_result_json
from app.database import async_session_factory
from app.models.article import Article
from app.models.crawl_log import CrawlLog
from app.models.source import Source

logger = logging.getLogger(__name__)


async def execute_crawl_job(source_config: dict[str, Any]) -> None:
    """Execute a crawl for a single source. Called by APScheduler."""
    source_id = source_config["id"]
    logger.info("Starting crawl: %s", source_id)

    try:
        crawler = CrawlerRegistry.create_crawler(source_config)
    except Exception as e:
        logger.error("Failed to create crawler for %s: %s", source_id, e)
        # Still record a failed CrawlLog so the failure is visible via API
        async with async_session_factory() as session:
            log = CrawlLog(
                source_id=source_id,
                status=CrawlStatus.FAILED.value,
                items_total=0,
                items_new=0,
                error_message=f"Crawler creation failed: {e}",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                duration_seconds=0.0,
            )
            session.add(log)
            await session.commit()
        return

    async with async_session_factory() as session:
        result = await crawler.run(db_session=session)

        # Persist new articles
        for item in result.items:
            article = Article(
                source_id=item.source_id or source_id,
                dimension=item.dimension or source_config.get("dimension", ""),
                url=item.url,
                url_hash=compute_url_hash(item.url),
                title=item.title,
                summary=item.summary,
                content=item.content,
                content_hash=item.content_hash,
                author=item.author,
                published_at=item.published_at,
                tags=list(set(item.tags + source_config.get("tags", []))),
                extra=item.extra,
            )
            session.add(article)

        # Save to local JSON (independent of DB)
        try:
            save_crawl_result_json(result, source_config)
        except Exception as e:
            logger.warning("Failed to save JSON for %s: %s", source_id, e)

        # Log the crawl result
        log = CrawlLog(
            source_id=source_id,
            status=result.status.value,
            items_total=result.items_total,
            items_new=result.items_new,
            error_message=result.error_message,
            started_at=result.started_at,
            finished_at=result.finished_at,
            duration_seconds=result.duration_seconds,
        )
        session.add(log)

        # Update source status
        now = datetime.now(timezone.utc)
        from sqlalchemy import update

        update_values: dict[str, Any] = {"last_crawl_at": now}
        if result.status in (CrawlStatus.SUCCESS, CrawlStatus.NO_NEW_CONTENT):
            update_values["last_success_at"] = now
            update_values["consecutive_failures"] = 0
        else:
            update_values["consecutive_failures"] = Source.consecutive_failures + 1

        await session.execute(
            update(Source).where(Source.id == source_id).values(**update_values)
        )

        await session.commit()

    logger.info(
        "Crawl complete: %s | status=%s | new=%d/%d | duration=%.1fs",
        source_id,
        result.status.value,
        result.items_new,
        result.items_total,
        result.duration_seconds,
    )
