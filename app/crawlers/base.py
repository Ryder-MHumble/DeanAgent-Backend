from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

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
    content_html: str | None = None
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

    async def run(self) -> CrawlResult:
        """Orchestrate: timing, error handling, logging."""
        result = CrawlResult(source_id=self.source_id)
        result.started_at = datetime.now(timezone.utc)
        try:
            items = await self.fetch_and_parse()
            result.items_total = len(items)
            result.items_all = items
            result.items = items
            result.items_new = len(items)
            if items:
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
