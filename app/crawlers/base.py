from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crawlers.utils.dedup import compute_url_hash

logger = logging.getLogger(__name__)


class CrawlStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NO_NEW_CONTENT = "no_new_content"


@dataclass
class CrawledItem:
    """A single article/item extracted by a crawler."""

    title: str
    url: str
    published_at: datetime | None = None
    author: str | None = None
    content: str | None = None
    content_hash: str | None = None
    source_id: str | None = None
    dimension: str | None = None
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawlResult:
    """Result of a single crawl execution for one source."""

    source_id: str
    status: CrawlStatus = CrawlStatus.SUCCESS
    items: list[CrawledItem] = field(default_factory=list)
    items_all: list[CrawledItem] = field(default_factory=list)
    items_new: int = 0
    items_total: int = 0
    error_message: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    duration_seconds: float = 0.0


class BaseCrawler(ABC):
    """Abstract base for all crawlers."""

    def __init__(self, source_config: dict[str, Any]) -> None:
        self.config = source_config
        self.source_id: str = source_config["id"]

    async def run(self, db_session: AsyncSession | None = None) -> CrawlResult:
        """Orchestrate: timing, error handling, dedup, logging.

        When db_session is None, dedup is skipped and all items are returned.
        """
        result = CrawlResult(source_id=self.source_id)
        result.started_at = datetime.now(timezone.utc)
        try:
            items = await self.fetch_and_parse()
            result.items_total = len(items)
            result.items_all = items
            if db_session is not None:
                new_items = await self._dedup(items, db_session)
            else:
                new_items = items
            result.items = new_items
            result.items_new = len(new_items)
            if new_items:
                result.status = CrawlStatus.SUCCESS
            else:
                result.status = CrawlStatus.NO_NEW_CONTENT
        except Exception as e:
            logger.exception("Crawl failed for source %s", self.source_id)
            result.status = CrawlStatus.FAILED
            result.error_message = str(e)
        finally:
            result.finished_at = datetime.now(timezone.utc)
            result.duration_seconds = (result.finished_at - result.started_at).total_seconds()
        return result

    @abstractmethod
    async def fetch_and_parse(self) -> list[CrawledItem]:
        """Subclasses implement: fetch the source, parse, return items."""
        ...

    async def _dedup(
        self, items: list[CrawledItem], db_session: AsyncSession
    ) -> list[CrawledItem]:
        """Check URL hashes against existing articles in DB."""
        if not items:
            return []

        from app.models.article import Article

        url_hashes = [compute_url_hash(item.url) for item in items]
        stmt = select(Article.url_hash).where(Article.url_hash.in_(url_hashes))
        result = await db_session.execute(stmt)
        existing_hashes = {row[0] for row in result.fetchall()}

        new_items = []
        for item, url_hash in zip(items, url_hashes):
            if url_hash not in existing_hashes:
                new_items.append(item)
        return new_items
