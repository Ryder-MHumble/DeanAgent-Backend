"""Faculty crawler — extracts teacher/researcher profiles from university department pages.

Config fields:
  - url: faculty list page URL
  - base_url: for resolving relative links
  - use_playwright: bool (default False) — use Playwright for JS-rendered pages
  - wait_for: CSS selector to wait for (only when use_playwright=True)
  - wait_timeout: milliseconds (default 15000, only when use_playwright=True)
  - faculty_selectors:
      list_item: CSS selector for each faculty entry (required)
      name: selector for name (default "h2"), relative to list_item
      bio: selector for bio/intro text (optional)
      link: selector for profile link (default "a")
      photo: selector for photo img (optional)
      position: selector for position/title (optional, only if separate from name)
      email: selector for email address (optional)
  - detail_selectors: (optional) fetch individual profile pages for richer info
      name: selector for name override
      position: selector for position/title
      bio: selector for bio/intro
      research_areas: selector for research directions text
      email: selector for email address
      photo: selector for photo img src
  - university: university full name (stored in ScholarRecord.university)
  - department: department full name (stored in ScholarRecord.department)
  - request_delay: seconds between detail page requests (default 1.0)

CrawledItem mapping (for pipeline compatibility):
  - title    = ScholarRecord.name
  - url      = ScholarRecord.profile_url  (dedup key)
  - content  = ScholarRecord.bio
  - extra    = ScholarRecord.model_dump() — full structured record

Schema: see app/schemas/scholar.py → ScholarRecord
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.crawlers.base import BaseCrawler, CrawledItem
from app.crawlers.utils.dedup import compute_content_hash, compute_url_hash
from app.crawlers.utils.http_client import fetch_page
from app.schemas.scholar import (
    ScholarRecord,
    compute_scholar_completeness,
    parse_research_areas,
)

logger = logging.getLogger(__name__)

# Regex for extracting email addresses from text
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_valid_href(href: str) -> bool:
    """Return True if href is a real navigable URL (not javascript:, #, empty)."""
    if not href:
        return False
    href_lower = href.strip().lower()
    if href_lower.startswith("javascript:") or href_lower == "#":
        return False
    return True


def _resolve_url(href: str, base_url: str) -> str:
    """Resolve a potentially relative href against base_url."""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(base_url, href)


def _extract_text(el: BeautifulSoup | None, selector: str | None) -> str:
    """Extract stripped text from a sub-element found by selector."""
    if el is None or not selector:
        return ""
    found = el.select_one(selector)
    return found.get_text(strip=True) if found else ""


def _extract_img_src(el: BeautifulSoup | None, selector: str | None, base_url: str) -> str:
    """Extract and resolve an img src from a sub-element found by selector."""
    if el is None or not selector:
        return ""
    img = el.select_one(selector)
    if img is None:
        return ""
    src = img.get("src", "").strip()
    if not src:
        return ""
    return _resolve_url(src, base_url)


def _extract_email_from_text(text: str) -> str:
    """Find the first email address in text."""
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else ""


class FacultyCrawler(BaseCrawler):
    """Crawler for university faculty/staff list pages.

    Extracts structured faculty profile data and stores it as a ScholarRecord
    (app.schemas.scholar) in CrawledItem.extra. All missing fields default to
    "" / [] / -1 so the output is always schema-complete and DB-migration-ready.
    """

    async def _fetch_html_static(self, url: str) -> str:
        return await fetch_page(
            url,
            headers=self.config.get("headers"),
            encoding=self.config.get("encoding"),
            request_delay=self.config.get("request_delay"),
        )

    async def _fetch_html_playwright(self, url: str) -> str:
        from app.crawlers.utils.playwright_pool import get_page

        wait_for = self.config.get("wait_for", "networkidle")
        wait_timeout = self.config.get("wait_timeout", 15000)

        async with get_page() as page:
            await page.goto(url, wait_until="domcontentloaded", timeout=wait_timeout)
            if wait_for == "networkidle":
                await page.wait_for_load_state("networkidle", timeout=wait_timeout)
            else:
                try:
                    await page.wait_for_selector(wait_for, timeout=wait_timeout)
                except Exception:
                    pass
            return await page.content()

    async def _fetch_detail(self, profile_url: str, detail_selectors: dict) -> dict:
        """Fetch individual profile page and extract detailed faculty info."""
        result: dict = {}
        try:
            html = await self._fetch_html_static(profile_url)
            soup = BeautifulSoup(html, "lxml")

            if name_sel := detail_selectors.get("name"):
                if name_text := _extract_text(soup, name_sel):
                    result["name"] = name_text

            if pos_sel := detail_selectors.get("position"):
                if pos_text := _extract_text(soup, pos_sel):
                    result["position"] = pos_text

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

            if photo_sel := detail_selectors.get("photo"):
                base = self.config.get("base_url", profile_url)
                if photo_url := _extract_img_src(soup, photo_sel, base):
                    result["photo_url"] = photo_url

            # heading_sections: {field: "heading text"} — find h2/h3/h4/p by text, extract next sibling
            # Useful for pages where sections are identified by heading text (common on Chinese academic sites)
            if heading_sections := detail_selectors.get("heading_sections"):
                for field, heading_text in heading_sections.items():
                    # Check both heading tags (h2/h3/h4) and paragraph tags (some sites use p for headings)
                    for tag in soup.find_all(["h2", "h3", "h4", "p"]):
                        if tag.get_text(strip=True) == heading_text:
                            # Look for content in next sibling or parent's next sibling
                            sibling = tag.find_next_sibling()
                            if sibling:
                                text = sibling.get_text(strip=True)
                                if text:
                                    if field == "research_areas":
                                        result[field] = parse_research_areas(text)
                                    else:
                                        result[field] = text
                            break

        except Exception as e:
            logger.warning("Failed to fetch faculty detail %s: %s", profile_url, e)
        return result

    async def fetch_and_parse(self) -> list[CrawledItem]:
        url = self.config["url"]
        base_url = self.config.get("base_url", url)
        use_playwright = self.config.get("use_playwright", False)
        faculty_sel = self.config.get("faculty_selectors", {})
        detail_selectors = self.config.get("detail_selectors")
        request_delay = self.config.get("request_delay", 1.0)

        university = self.config.get("university", "")
        department = self.config.get("department", "")
        source_id = self.source_id
        crawled_at = _now_iso()

        # 1. Fetch faculty list page
        if use_playwright:
            html = await self._fetch_html_playwright(url)
        else:
            html = await self._fetch_html_static(url)

        soup = BeautifulSoup(html, "lxml")

        # 2. Locate faculty entries
        list_item_sel = faculty_sel.get("list_item", "li")
        entries = soup.select(list_item_sel)

        if not entries:
            logger.warning(
                "FacultyCrawler[%s]: no entries found with selector %r on %s",
                self.source_id, list_item_sel, url,
            )

        name_sel = faculty_sel.get("name", "h2")
        bio_sel = faculty_sel.get("bio")
        link_sel = faculty_sel.get("link", "a")
        photo_sel = faculty_sel.get("photo")
        position_sel = faculty_sel.get("position")
        email_sel = faculty_sel.get("email")

        items: list[CrawledItem] = []
        seen_urls: set[str] = set()

        for entry in entries:
            # --- Name ---
            name_text = _extract_text(entry, name_sel)
            if not name_text:
                continue

            # --- Profile URL ---
            profile_url = ""
            if link_sel:
                link_el = entry.select_one(link_sel)
                if link_el:
                    href = link_el.get("href", "").strip()
                    if _is_valid_href(href):
                        profile_url = _resolve_url(href, base_url)

            # Synthetic URL for faculty without real profile pages
            if not profile_url:
                name_hash = compute_url_hash(f"{url}#{name_text}")
                profile_url = f"{url}#{name_hash[:16]}"

            # Skip exact duplicates (same profile URL)
            if profile_url in seen_urls:
                continue
            seen_urls.add(profile_url)

            # --- Fields from list page ---
            position_text = _extract_text(entry, position_sel) if position_sel else ""
            bio_text = _extract_text(entry, bio_sel) if bio_sel else ""
            photo_url = _extract_img_src(entry, photo_sel, base_url) if photo_sel else ""
            email_text = _extract_text(entry, email_sel) if email_sel else ""
            research_areas: list[str] = []

            # --- Optional: fetch detail page ---
            if detail_selectors and not profile_url.startswith(f"{url}#"):
                if request_delay:
                    await asyncio.sleep(request_delay)
                detail = await self._fetch_detail(profile_url, detail_selectors)
                if detail.get("name"):
                    name_text = detail["name"]
                if detail.get("bio"):
                    bio_text = detail["bio"]
                if detail.get("position"):
                    position_text = detail["position"]
                if detail.get("email"):
                    email_text = detail["email"]
                if detail.get("photo_url"):
                    photo_url = detail["photo_url"]
                if detail.get("research_areas"):
                    research_areas = detail["research_areas"]

            # --- Build ScholarRecord ---
            record = ScholarRecord(
                # 基本信息
                name=name_text,
                photo_url=photo_url,
                # 机构归属
                university=university,
                department=department,
                # 职称
                position=position_text,
                # 研究
                research_areas=research_areas,
                bio=bio_text,
                # 联系方式
                email=email_text,
                # 主页链接
                profile_url=profile_url,
                # 元信息
                source_id=source_id,
                source_url=url,
                crawled_at=crawled_at,
                last_seen_at=crawled_at,
                is_active=True,
            )
            record.data_completeness = compute_scholar_completeness(record)

            content_hash = compute_content_hash(bio_text) if bio_text else None

            items.append(
                CrawledItem(
                    title=name_text,
                    url=profile_url,
                    published_at=None,
                    author=None,
                    content=bio_text or None,
                    content_hash=content_hash,
                    source_id=source_id,
                    dimension=self.config.get("dimension"),
                    tags=self.config.get("tags", []),
                    extra=record.model_dump(),
                )
            )

        logger.info(
            "FacultyCrawler[%s]: extracted %d faculty from %s",
            self.source_id, len(items), url,
        )
        return items
