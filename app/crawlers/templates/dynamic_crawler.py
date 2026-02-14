from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from app.crawlers.base import BaseCrawler, CrawledItem
from app.crawlers.utils.http_client import fetch_page as http_fetch_page
from app.crawlers.utils.selector_parser import parse_detail_html, parse_list_items

logger = logging.getLogger(__name__)


class DynamicPageCrawler(BaseCrawler):
    """
    Template crawler for JS-rendered pages via Playwright.
    Uses same selector pattern as StaticHTMLCrawler but renders with Playwright first.

    Config fields (same as StaticHTMLCrawler plus):
      - wait_for: CSS selector or "networkidle" to wait for
      - wait_timeout: milliseconds (default 10000)
      - detail_use_playwright: bool (default True) — use Playwright or httpx for detail pages
    """

    async def _fetch_detail_with_playwright(
        self, page: Any, detail_url: str, detail_selectors: dict, wait_timeout: int,
    ) -> tuple[str | None, str | None, str | None, str | None]:
        """Fetch a detail page using Playwright (same context, shares cookies).

        Returns (content, summary, author, content_hash).
        """
        try:
            await page.goto(detail_url, wait_until="load", timeout=wait_timeout)
            await page.wait_for_load_state("networkidle", timeout=wait_timeout)
            detail_wait = detail_selectors.get("content", "body")
            try:
                await page.wait_for_selector(detail_wait, timeout=5000)
            except Exception:
                pass  # Content may already be available or selector optional
            detail_html = await page.content()

            detail = parse_detail_html(detail_html, detail_selectors)
            return detail.content, detail.summary, detail.author, detail.content_hash
        except Exception as e:
            logger.warning("Failed to fetch detail page %s: %s", detail_url, e)
            return None, None, None, None

    async def _fetch_detail_with_httpx(
        self, detail_url: str, detail_selectors: dict,
    ) -> tuple[str | None, str | None, str | None, str | None]:
        """Fetch a detail page using httpx (faster, for sites without JS protection).

        Returns (content, summary, author, content_hash).
        """
        try:
            detail_html = await http_fetch_page(
                detail_url,
                headers=self.config.get("headers"),
                encoding=self.config.get("encoding"),
                request_delay=self.config.get("request_delay"),
            )
            detail = parse_detail_html(detail_html, detail_selectors)
            return detail.content, detail.summary, detail.author, detail.content_hash
        except Exception as e:
            logger.warning("Failed to fetch detail page %s: %s", detail_url, e)
            return None, None, None, None

    async def fetch_and_parse(self) -> list[CrawledItem]:
        from app.crawlers.utils.playwright_pool import get_page

        url = self.config["url"]
        selectors = self.config.get("selectors", {})
        base_url = self.config.get("base_url", url)
        keyword_filter = self.config.get("keyword_filter", [])
        detail_selectors = self.config.get("detail_selectors")
        detail_use_playwright = self.config.get("detail_use_playwright", True)
        wait_for = self.config.get("wait_for", "networkidle")
        wait_timeout = self.config.get("wait_timeout", 10000)

        async with get_page() as page:
            await page.goto(url, wait_until="domcontentloaded", timeout=wait_timeout)

            if wait_for == "networkidle":
                await page.wait_for_load_state("networkidle", timeout=wait_timeout)
            else:
                await page.wait_for_selector(wait_for, timeout=wait_timeout)

            html = await page.content()

            soup = BeautifulSoup(html, "lxml")
            raw_items = parse_list_items(soup, selectors, base_url, keyword_filter)

            items: list[CrawledItem] = []
            for raw in raw_items:
                content = summary = author = content_hash = None
                if detail_selectors:
                    if detail_use_playwright:
                        content, summary, author, content_hash = (
                            await self._fetch_detail_with_playwright(
                                page, raw.url, detail_selectors, wait_timeout,
                            )
                        )
                    else:
                        content, summary, author, content_hash = (
                            await self._fetch_detail_with_httpx(
                                raw.url, detail_selectors,
                            )
                        )

                items.append(
                    CrawledItem(
                        title=raw.title,
                        url=raw.url,
                        published_at=raw.published_at,
                        author=author,
                        summary=summary,
                        content=content,
                        content_hash=content_hash,
                        source_id=self.source_id,
                        dimension=self.config.get("dimension"),
                        tags=self.config.get("tags", []),
                    )
                )

        return items
