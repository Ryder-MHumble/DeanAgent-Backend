"""PDF URL extraction utilities."""
from __future__ import annotations

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_pdf_url(
    soup: BeautifulSoup,
    page_url: str,
    title: str,
    config: dict,
) -> str | None:
    """
    Extract PDF URL from a page.

    Args:
        soup: BeautifulSoup object of the page
        page_url: Current page URL (for relative path conversion)
        title: Article title (for smart matching)
        config: Source configuration from YAML

    Returns:
        Absolute PDF URL if found, None otherwise

    Extraction strategies (priority order):
        1. CSS selector (config['pdf_selector'])
        2. Smart matching (automatic)
    """
    try:
        # Strategy 1: CSS selector from config
        if pdf_selector := config.get("pdf_selector"):
            return _extract_with_selector(soup, page_url, pdf_selector)

        # Strategy 2: Smart matching
        return _smart_match_pdf(soup, page_url, title)

    except Exception as e:
        logger.warning(f"PDF extraction failed for {page_url}: {e}")
        return None


def _extract_with_selector(
    soup: BeautifulSoup,
    page_url: str,
    selector: str,
) -> str | None:
    """Extract PDF using CSS selector."""
    link = soup.select_one(selector)
    if not link:
        return None

    href = link.get("href")
    if not href:
        return None

    # Convert relative URL to absolute
    return urljoin(page_url, href)


def _smart_match_pdf(
    soup: BeautifulSoup,
    page_url: str,
    title: str,
) -> str | None:
    """
    Smart match PDF links in page.

    Finds all links ending with .pdf and returns the first one.
    """
    # Find all <a> tags
    links = soup.find_all("a", href=True)

    for link in links:
        href = link.get("href", "")
        if href.lower().endswith(".pdf"):
            return urljoin(page_url, href)

    return None
