from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.crawlers.base import BaseCrawler, CrawledItem
from app.crawlers.utils.dedup import compute_content_hash
from app.crawlers.utils.http_client import fetch_page
from app.crawlers.utils.text_extract import html_to_text, truncate_summary

logger = logging.getLogger(__name__)


class StaticHTMLCrawler(BaseCrawler):
    """
    Template crawler for static HTML list pages via requests + BeautifulSoup4.

    Config fields:
      - url: list page URL
      - selectors:
          list_item: CSS selector for each article entry
          title: CSS selector for title (relative to list_item), or "_self"
          link: CSS selector for link (relative to list_item), or "_self"
          link_attr: attribute for link (default "href")
          date: CSS selector for date (relative to list_item)
          date_format: strptime format (e.g., "%Y-%m-%d")
          date_regex: optional regex to extract date string before parsing
      - base_url: for resolving relative links
      - encoding: page encoding override
      - keyword_filter: optional keywords
      - detail_selectors: (optional) for fetching detail pages
          content: CSS selector for article body
          author: CSS selector for author
      - headers: custom HTTP headers
      - request_delay: seconds between requests

    Special selector values:
      "_self" — use the list_item element itself (for pages where <a> is the list item)
    """

    @staticmethod
    def _extract_date(el, selectors: dict) -> datetime | None:
        """Extract date from an element using selector + format + optional regex.

        Tries plain get_text first (handles inline dates like "2026/02/13"),
        falls back to separator=" " (handles split dates like <p>12</p><span>2026.02</span>).
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

        # Try two extraction strategies: plain text first, then with separator
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
        url = self.config["url"]
        selectors = self.config.get("selectors", {})
        base_url = self.config.get("base_url", url)
        keyword_filter = self.config.get("keyword_filter", [])
        detail_selectors = self.config.get("detail_selectors")

        html = await fetch_page(
            url,
            headers=self.config.get("headers"),
            encoding=self.config.get("encoding"),
            request_delay=self.config.get("request_delay"),
        )

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
            link_attr = selectors.get("link_attr", "href")
            raw_link = link_el.get(link_attr, "")
            if not raw_link:
                continue
            link = urljoin(base_url, raw_link)

            # Keyword filtering
            if keyword_filter and not any(kw in title for kw in keyword_filter):
                continue

            # Extract date
            published_at = self._extract_date(el, selectors)

            # Optionally fetch detail page for full content
            content = None
            summary = None
            author = None
            content_hash = None

            if detail_selectors:
                try:
                    detail_html = await fetch_page(
                        link,
                        headers=self.config.get("headers"),
                        encoding=self.config.get("encoding"),
                        request_delay=self.config.get("request_delay"),
                    )
                    detail_soup = BeautifulSoup(detail_html, "lxml")

                    if content_sel := detail_selectors.get("content"):
                        content_el = detail_soup.select_one(content_sel)
                        if content_el:
                            content = html_to_text(str(content_el))
                            summary = truncate_summary(content)
                            content_hash = compute_content_hash(content)

                    if author_sel := detail_selectors.get("author"):
                        author_el = detail_soup.select_one(author_sel)
                        if author_el:
                            author = author_el.get_text(strip=True)
                except Exception as e:
                    logger.warning("Failed to fetch detail page %s: %s", link, e)

            items.append(
                CrawledItem(
                    title=title,
                    url=link,
                    published_at=published_at,
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
