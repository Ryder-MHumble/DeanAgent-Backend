"""Shared HTML parsing logic for template crawlers (static & dynamic).

Extracts date, list items, and detail page content from BeautifulSoup elements.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.utils.dedup import compute_content_hash
from app.crawlers.utils.text_extract import html_to_text, truncate_summary


@dataclass
class RawListItem:
    """Intermediate result from parsing a list page element."""

    title: str
    url: str
    published_at: datetime | None = None


@dataclass
class DetailResult:
    """Result from parsing a detail page."""

    content: str | None = None
    summary: str | None = None
    author: str | None = None
    content_hash: str | None = None


def extract_date(el: Tag, selectors: dict) -> datetime | None:
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

    for date_text in (
        date_el.get_text(strip=True),
        date_el.get_text(separator=" ", strip=True),
    ):
        text = date_text
        if date_regex:
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


def _normalize_base_url(base_url: str) -> str:
    """Ensure base_url ends with '/' so urljoin treats the last segment as a directory.

    Without a trailing slash, urljoin treats the last path segment as a file
    and drops it when resolving relative links (e.g., ./202602/xxx.html).
    """
    parsed = urlparse(base_url)
    path = parsed.path
    if not path or path.endswith("/"):
        return base_url
    # If the last segment contains a dot, treat it as a file (e.g., index.html)
    last_segment = path.rsplit("/", 1)[-1]
    if "." in last_segment:
        return base_url
    return urlunparse(parsed._replace(path=path + "/"))


def parse_list_items(
    soup: BeautifulSoup,
    selectors: dict,
    base_url: str,
    keyword_filter: list[str] | None = None,
) -> list[RawListItem]:
    """Parse a list page and extract title, link, and date for each item.

    Supports the "_self" convention: if title/link selector is "_self",
    the list_item element itself is used.
    """
    base_url = _normalize_base_url(base_url)
    list_elements = soup.select(selectors.get("list_item", "li"))
    items: list[RawListItem] = []

    for el in list_elements:
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
        url = urljoin(base_url, raw_link)

        # Keyword filtering
        if keyword_filter and not any(kw in title for kw in keyword_filter):
            continue

        published_at = extract_date(el, selectors)

        items.append(RawListItem(title=title, url=url, published_at=published_at))

    return items


def parse_detail_html(html: str, detail_selectors: dict) -> DetailResult:
    """Parse a detail page HTML and extract content, summary, author, content_hash."""
    detail_soup = BeautifulSoup(html, "lxml")
    result = DetailResult()

    if content_sel := detail_selectors.get("content"):
        content_el = detail_soup.select_one(content_sel)
        if content_el:
            result.content = html_to_text(str(content_el))
            result.summary = truncate_summary(result.content)
            result.content_hash = compute_content_hash(result.content)

    if author_sel := detail_selectors.get("author"):
        author_el = detail_soup.select_one(author_sel)
        if author_el:
            result.author = author_el.get_text(strip=True)

    return result
