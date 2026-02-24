from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.crawlers.base import CrawlStatus
from app.crawlers.registry import CrawlerRegistry
from app.crawlers.utils.json_storage import save_crawl_result_json

logger = logging.getLogger(__name__)


def _is_db_available() -> bool:
    """Check if the scheduler manager reports DB availability."""
    from app.scheduler.manager import get_scheduler_manager

    mgr = get_scheduler_manager()
    return mgr.db_available if mgr else False


async def _persist_to_db(result, source_config: dict[str, Any]) -> None:
    """Persist crawl results to database. Only called when DB is available."""
    from sqlalchemy import update
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.crawlers.utils.dedup import compute_url_hash
    from app.database import async_session_factory
    from app.models.article import Article
    from app.models.crawl_log import CrawlLog
    from app.models.source import Source

    source_id = source_config["id"]

    async with async_session_factory() as session:
        # Persist new articles
        for item in result.items:
            stmt = pg_insert(Article).values(
                source_id=item.source_id or source_id,
                dimension=item.dimension or source_config.get("dimension", ""),
                url=item.url,
                url_hash=compute_url_hash(item.url),
                title=item.title,
                content=item.content,
                content_html=item.content_html,
                content_hash=item.content_hash,
                author=item.author,
                published_at=item.published_at,
                tags=list(set(item.tags + source_config.get("tags", []))),
                extra=item.extra,
            ).on_conflict_do_nothing(index_elements=["url_hash"])
            await session.execute(stmt)

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


async def execute_crawl_job(source_config: dict[str, Any]) -> None:
    """Execute a crawl for a single source. Called by APScheduler."""
    source_id = source_config["id"]
    logger.info("Starting crawl: %s", source_id)

    try:
        crawler = CrawlerRegistry.create_crawler(source_config)
    except Exception as e:
        logger.error("Failed to create crawler for %s: %s", source_id, e)
        # Record failure to DB if available
        if _is_db_available():
            try:
                from app.database import async_session_factory
                from app.models.crawl_log import CrawlLog

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
            except Exception as db_err:
                logger.warning("Failed to log crawl error to DB: %s", db_err)
        return

    # Run crawler (db_session=None skips dedup, which is fine for file-only mode)
    result = await crawler.run(db_session=None)

    # Save to local JSON (always)
    try:
        save_crawl_result_json(result, source_config)
    except Exception as e:
        logger.warning("Failed to save JSON for %s: %s", source_id, e)

    # Persist to DB (only when available)
    if _is_db_available():
        try:
            await _persist_to_db(result, source_config)
        except Exception as e:
            logger.warning("Failed to persist to DB for %s: %s (JSON saved)", source_id, e)

    logger.info(
        "Crawl complete: %s | status=%s | new=%d/%d | duration=%.1fs",
        source_id,
        result.status.value,
        result.items_new,
        result.items_total,
        result.duration_seconds,
    )
