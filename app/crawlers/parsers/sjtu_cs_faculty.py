"""SJTU CS faculty parser — fetches teacher list via AJAX POST endpoint.

SJTU CS (上海交通大学计算机学院) uses a JavaScript-driven faculty list page.
This parser calls the AJAX POST endpoint directly to obtain all teacher records.

AJAX endpoint: https://www.cs.sjtu.edu.cn/active/ajax_teacher_list.html
POST data: page=1&cat_id=20&cat_code=jiaoshiml&type=1
Response: JSON with 'tab_html' (institute filter tabs) and 'content' (teacher list HTML)
Content structure: div.rc-item > .name-list > span > a (name + profile link)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.crawlers.base import BaseCrawler, CrawledItem
from app.crawlers.utils.dedup import compute_url_hash
from app.schemas.scholar import ScholarRecord, compute_scholar_completeness

logger = logging.getLogger(__name__)

_AJAX_URL = "https://www.cs.sjtu.edu.cn/active/ajax_teacher_list.html"
_AJAX_DATA = {
    "page": "1",
    "cat_id": "20",
    "cat_code": "jiaoshiml",
    "type": "1",
}
_BASE_URL = "https://www.cs.sjtu.edu.cn"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SJTUCSFacultyCrawler(BaseCrawler):
    """Crawler for SJTU CS faculty list via AJAX POST endpoint."""

    async def fetch_and_parse(self) -> list[CrawledItem]:
        university = self.config.get("university", "上海交通大学")
        department = self.config.get("department", "计算机科学与工程系")
        source_id = self.source_id
        source_url = self.config.get("url", _AJAX_URL)
        crawled_at = _now_iso()

        # Fetch faculty list via AJAX POST
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                    ),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": "https://www.cs.sjtu.edu.cn/jiaoshiml.html",
                },
            ) as client:
                response = await client.post(_AJAX_URL, data=_AJAX_DATA)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error("SJTUCSFacultyCrawler: AJAX request failed: %s", e)
            return []

        content_html = data.get("content", "")
        if not content_html:
            logger.warning("SJTUCSFacultyCrawler: empty content from AJAX response")
            return []

        soup = BeautifulSoup(content_html, "lxml")
        faculty_links = soup.select(".name-list span a")

        if not faculty_links:
            logger.warning("SJTUCSFacultyCrawler: no faculty links found in AJAX response")
            return []

        items: list[CrawledItem] = []
        seen_urls: set[str] = set()

        for a_tag in faculty_links:
            name_text = a_tag.get_text(strip=True)
            if not name_text:
                continue

            href = a_tag.get("href", "").strip()
            if href:
                profile_url = urljoin(_BASE_URL, href)
            else:
                # Synthetic URL for faculty without profile pages
                name_hash = compute_url_hash(f"{source_url}#{name_text}")
                profile_url = f"{source_url}#{name_hash[:16]}"

            if profile_url in seen_urls:
                continue
            seen_urls.add(profile_url)

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

        logger.info(
            "SJTUCSFacultyCrawler: extracted %d faculty from AJAX endpoint",
            len(items),
        )
        return items
