"""ISCAS faculty parser — fetches researcher list from Chinese Academy of Sciences Institute of Software.

ISCAS (中国科学院软件研究所) faculty listing page contains structured or semi-structured lists
of researchers. This parser extracts researcher names from HTML links or text content
and optionally fetches their detail pages.

URL: http://www.iscas.ac.cn/rcdw2016/yjyzgjgcs2016/
"""
from __future__ import annotations

import asyncio
import logging
import re as _re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.crawlers.base import BaseCrawler, CrawledItem
from app.crawlers.utils.dedup import compute_url_hash
from app.crawlers.utils.http_client import fetch_page
from app.schemas.scholar import ScholarRecord, compute_scholar_completeness, parse_research_areas

logger = logging.getLogger(__name__)

_EMAIL_RE = _re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_CHINESE_NAME_RE = _re.compile(r"[\u4e00-\u9fff]{2,4}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_text(el: BeautifulSoup | None, selector: str | None) -> str:
    """Extract stripped text from a sub-element found by selector."""
    if el is None or not selector:
        return ""
    found = el.select_one(selector)
    return found.get_text(strip=True) if found else ""


def _extract_email_from_text(text: str) -> str:
    """Find the first email address in text."""
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else ""


class ISCASFacultyCrawler(BaseCrawler):
    """Crawler for ISCAS (Institute of Software, Chinese Academy of Sciences) faculty list."""

    async def _fetch_detail(self, profile_url: str, detail_selectors: dict) -> dict:
        """Fetch individual profile page and extract detailed faculty info."""
        result: dict = {}
        try:
            html = await fetch_page(profile_url)
            soup = BeautifulSoup(html, "lxml")

            if bio_sel := detail_selectors.get("bio"):
                if bio_text := _extract_text(soup, bio_sel):
                    result["bio"] = bio_text

            if ra_sel := detail_selectors.get("research_areas"):
                if ra_text := _extract_text(soup, ra_sel):
                    result["research_areas"] = parse_research_areas(ra_text)

            if email_sel := detail_selectors.get("email"):
                if email_text := _extract_text(soup, email_sel):
                    result["email"] = email_text
            if not result.get("email"):
                full_text = soup.get_text()
                if email := _extract_email_from_text(full_text):
                    result["email"] = email

            if pos_sel := detail_selectors.get("position"):
                if pos_text := _extract_text(soup, pos_sel):
                    result["position"] = pos_text

        except Exception as e:
            logger.debug("Failed to fetch faculty detail %s: %s", profile_url, e)
        return result

    async def fetch_and_parse(self) -> list[CrawledItem]:
        university = self.config.get("university", "中国科学院")
        department = self.config.get("department", "软件研究所")
        source_id = self.source_id
        source_url = self.config.get("url")
        crawled_at = _now_iso()
        base_url = self.config.get("base_url", source_url)

        # Fetch page
        try:
            html = await fetch_page(source_url)
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            logger.error("ISCASFacultyCrawler: failed to fetch %s: %s", source_url, e)
            return []

        # Phase 1: Extract faculty links and names
        items: list[CrawledItem] = []
        seen_urls: set[str] = set()

        # Try multiple selectors to find faculty elements
        faculty_elements = soup.select(
            "ul li a, div.faculty a, p a, div.content a, table a"
        )

        # Fallback: extract Chinese names (2-4 characters) if no clear links found
        if not faculty_elements:
            text = soup.get_text()
            names = _CHINESE_NAME_RE.findall(text)
            # Filter to likely actual names (avoid single-char matches, remove duplicates)
            seen_names = set()
            faculty_elements = []
            for name in names:
                if name not in seen_names and len(name) >= 2:
                    seen_names.add(name)
                    # Create pseudo-element with name attribute
                    faculty_elements.append({"name": name})

        detail_selectors = self.config.get("detail_selectors", {})
        request_delay = self.config.get("request_delay", 1.0)

        for elem in faculty_elements:
            # Handle HTML element (a tag)
            if hasattr(elem, "get_text"):
                name_text = elem.get_text(strip=True)
                href = elem.get("href", "").strip() if hasattr(elem, "get") else ""
            else:
                # Handle dict (extracted name from text)
                name_text = elem.get("name", "")
                href = ""

            if not name_text or len(name_text) < 2:
                continue

            # Construct profile URL
            if href and href.startswith("http"):
                profile_url = href
            elif href:
                profile_url = urljoin(base_url, href)
            else:
                # Synthetic URL for faculty without profile pages
                name_hash = compute_url_hash(f"{source_url}#{name_text}")
                profile_url = f"{source_url}#{name_hash[:16]}"

            if profile_url in seen_urls:
                continue
            seen_urls.add(profile_url)

            # Optional: fetch detail page
            bio_text = ""
            position_text = ""
            email_text = ""
            research_areas: list[str] = []

            if (
                detail_selectors
                and not profile_url.startswith(f"{source_url}#")
            ):
                if request_delay:
                    await asyncio.sleep(request_delay)
                detail = await self._fetch_detail(profile_url, detail_selectors)
                bio_text = detail.get("bio", "")
                position_text = detail.get("position", "")
                email_text = detail.get("email", "")
                research_areas = detail.get("research_areas", [])

            # Construct ScholarRecord
            record = ScholarRecord(
                name=name_text,
                university=university,
                department=department,
                profile_url=profile_url,
                source_id=source_id,
                source_url=source_url,
                crawled_at=crawled_at,
                last_seen_at=crawled_at,
                is_active=True,
                bio=bio_text,
                position=position_text,
                email=email_text,
                research_areas=research_areas,
            )
            record.data_completeness = compute_scholar_completeness(record)

            items.append(
                CrawledItem(
                    title=name_text,
                    url=profile_url,
                    published_at=None,
                    author=None,
                    content=None,
                    content_hash=None,
                    source_id=source_id,
                    dimension=self.config.get("dimension"),
                    tags=self.config.get("tags", []),
                    extra=record.model_dump(),
                )
            )

        logger.info("ISCASFacultyCrawler: extracted %d faculty", len(items))
        return items
