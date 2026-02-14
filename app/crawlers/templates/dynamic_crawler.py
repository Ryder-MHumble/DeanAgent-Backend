from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.crawlers.base import BaseCrawler, CrawledItem
from app.crawlers.utils.dedup import compute_content_hash
from app.crawlers.utils.text_extract import html_to_text, truncate_summary

logger = logging.getLogger(__name__)


class DynamicPageCrawler(BaseCrawler):
    """
    Template crawler for JS-rendered pages via Playwright.
    Uses same selector pattern as StaticHTMLCrawler but renders with Playwright first.

    Config fields (same as StaticHTMLCrawler plus):
      - wait_for: CSS selector or "networkidle" to wait for
      - wait_timeout: milliseconds (default 10000)
    """

    @staticmethod
    def _extract_date(el, selectors: dict) -> datetime | None:
        """Extract date from an element using selector + format + optional regex.

        Tries plain get_text first, falls back to separator=" " for split dates.
        """
        date_selector = selectors.get("date")
        if not date_selector:
            return None
        date_el = el.select_one(date_selector)
        if date_el is None:
            return None
        date_format = selectors.get("date_format")
        if not date_format:
            return None

        date_regex = selectors.get("date_regex")

        for date_text in (
            date_el.get_text(strip=True),
            date_el.get_text(separator=" ", strip=True),
        ):
            text = date_text
            if date_regex:
                import re
                m = re.search(date_regex, text)
                if m:
                    text = m.group(0)
                else:
                    continue
            try:
                return datetime.strptime(text, date_format)
            except ValueError:
                continue
        return None

    async def fetch_and_parse(self) -> list[CrawledItem]:
        from app.crawlers.utils.playwright_pool import get_page

        url = self.config["url"]
        selectors = self.config.get("selectors", {})
        base_url = self.config.get("base_url", url)
        keyword_filter = self.config.get("keyword_filter", [])
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
        list_items = soup.select(selectors.get("list_item", "li"))

        items: list[CrawledItem] = []
        for el in list_items:
            # Extract title ("_self" means use el itself)
            title_selector = selectors.get("title", "a")
            if title_selector == "_self":
                title_el = el
            else:
                title_el = el.select_one(title_selector) if title_selector else el
            if title_el is None:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            # Extract link ("_self" means use el itself)
            link_selector = selectors.get("link", "a")
            if link_selector == "_self":
                link_el = el
            else:
                link_el = el.select_one(link_selector) if link_selector else el
            if link_el is None:
                continue
            raw_link = link_el.get(selectors.get("link_attr", "href"), "")
            if not raw_link:
                continue
            link = urljoin(base_url, raw_link)

            if keyword_filter and not any(kw in title for kw in keyword_filter):
                continue

            published_at = self._extract_date(el, selectors)

            items.append(
                CrawledItem(
                    title=title,
                    url=link,
                    published_at=published_at,
                    source_id=self.source_id,
                    dimension=self.config.get("dimension"),
                    tags=self.config.get("tags", []),
                )
            )

        return items
