"""CVF Open Access 爬虫 — openaccess.thecvf.com

覆盖：CVPR / ICCV / WACV
数据源：https://openaccess.thecvf.com/{venue}{year}?day=all
特点：静态 HTML、结构稳定（<dt class="ptitle"> + <dd>authors</dd>）

⚠️ 不在 CVF Open Access 的会议：
- ECCV（在 ecva.net，独立 parser）
- CVPR Workshop 入口独立（/CVPR2024W），需单独 source

⚠️ Track 区分：
- CVF 列表页不区分 Oral/Highlight/Poster（要从 Session 页才有，成本高）
- 当前 parser 统一标为 "Main Conference"，track 精细化留给后续增强

⚠️ 接入基座：本文件搬到 `app/crawlers/parsers/cvf_openaccess.py`
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

try:
    from app.crawlers.base import BaseCrawler, CrawledItem
    from app.crawlers.utils.http_client import fetch_page
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from base import BaseCrawler, CrawledItem  # type: ignore

    async def fetch_page(
        url: str,
        timeout: float = 90.0,
        max_retries: int = 3,
        request_delay: float | None = None,
    ) -> str:
        import httpx
        last_err = None
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=timeout,
                    headers={"User-Agent": "Mozilla/5.0 (research data crawler)"},
                    follow_redirects=True,
                ) as client:
                    r = await client.get(url)
                    r.raise_for_status()
                    return r.text
            except Exception as e:
                last_err = e
                if attempt < max_retries:
                    await asyncio.sleep(3 ** attempt)
        raise last_err


logger = logging.getLogger(__name__)

BASE = "https://openaccess.thecvf.com"


_ARXIV_RE = re.compile(r'arxiv\.org/abs/(\d{4}\.\d{4,5})', re.I)


class CVFCrawler(BaseCrawler):
    """CVF Open Access 任意年 × 任意会议（CVPR/ICCV/WACV）。

    YAML 字段：
        id: cvpr-2024
        crawler_class: cvf_openaccess
        venue: CVPR
        year: 2024
        is_workshop: false   # True 时 URL 后缀加 W
    """

    async def fetch_and_parse(self) -> list[CrawledItem]:
        items: list[CrawledItem] = []
        for cfg in self._iter_year_configs():
            items.extend(await self._fetch_single_year(cfg))
        return items

    def _iter_year_configs(self) -> list[dict[str, Any]]:
        raw = self.config.get("year_configs")
        if isinstance(raw, list) and raw:
            return [{**self.config, **item} for item in raw if isinstance(item, dict)]
        return [self.config]

    async def _fetch_single_year(self, cfg: dict[str, Any]) -> list[CrawledItem]:
        if cfg.get("source_format") == "cvf_virtual_page":
            return await self._fetch_virtual_year(cfg)

        venue: str = cfg["venue"]
        year: int = int(cfg["year"])
        is_workshop: bool = cfg.get("is_workshop", False)

        # URL 模式
        workshop_suffix = "W" if is_workshop else ""
        list_url = str(cfg.get("url") or f"{BASE}/{venue}{year}{workshop_suffix}?day=all")

        logger.info(f"[{self.source_id}] fetching {list_url}")
        html = await fetch_page(list_url, timeout=90.0, max_retries=3)

        rows = self._parse_rows(html)
        logger.info(f"[{self.source_id}] parsed {len(rows)} papers")

        now = datetime.now(timezone.utc)
        items: list[CrawledItem] = []

        for row in rows:
            href = row["href"]
            title = row["title"]
            authors_list = row["authors"]
            link_hrefs = row["link_hrefs"]

            # 完整 URL
            detail_url = href if href.startswith('http') else f"{BASE}/{href}"

            # raw_id：从 href 抽 paper hash
            # content/CVPR2024/html/Author_Title_CVPR_2024_paper.html
            raw_id_m = re.search(r'/html/([^/]+)_paper\.html', href)
            raw_id = f"{venue}{year}/{raw_id_m.group(1)}" if raw_id_m else href
            paper_id = f"cvf:{raw_id}"

            # PDF
            pdf_url = next(
                (
                    self._absolutize(link)
                    for link in link_hrefs
                    if link.lower().endswith(".pdf")
                    and "supplemental/" not in link.lower()
                ),
                None,
            )
            # arXiv
            arxiv_id = next(
                (m.group(1) for link in link_hrefs if (m := _ARXIV_RE.search(link))),
                None,
            )
            authors_data = [
                {
                    "paper_id": paper_id,
                    "author_order": idx + 1,
                    "name_raw": a,
                    "name_normalized": a,
                    "source_author_id": None,
                    "author_url": None,
                    "affiliation": None,
                    "affiliation_country": None,
                    "email": None,
                    "orcid": None,
                    "scraped_at": now.isoformat(),
                    "schema_version": "1.0",
                }
                for idx, a in enumerate(authors_list)
            ]

            # Track 标注
            if is_workshop:
                track_label = "Workshop"
                is_main_track = False
            else:
                track_label = "Main Conference"
                is_main_track = True

            paper_data = {
                "paper_id": paper_id,
                "source": "cvf",
                "raw_id": raw_id,
                "venue": venue,
                "venue_full": _VENUE_FULL.get(venue, venue),
                "year": year,
                "track": track_label,
                "is_main_track": is_main_track,
                "is_workshop": is_workshop,
                "title": title,
                "abstract": None,
                "n_authors": len(authors_list),
                "url": detail_url,
                "pdf_url": pdf_url,
                "doi": None,
                "arxiv_id": arxiv_id,
                "scraped_at": now.isoformat(),
                "schema_version": "1.0",
            }

            items.append(
                CrawledItem(
                    title=title,
                    url=detail_url,
                    # CVPR 6月，ICCV 10月，WACV 1月；列表页没有逐篇日期。
                    published_at=datetime(year, 6, 1, tzinfo=timezone.utc),
                    author=authors_list[0] if authors_list else None,
                    source_id=self.source_id,
                    dimension=cfg.get("dimension", "academic_venues"),
                    tags=[venue, str(year), track_label],
                    extra={"paper": paper_data, "authors": authors_data},
                )
            )

        return items

    async def _fetch_virtual_year(self, cfg: dict[str, Any]) -> list[CrawledItem]:
        venue: str = cfg["venue"]
        year = int(cfg["year"])
        list_url = str(cfg["url"])
        html = await fetch_page(
            list_url,
            timeout=float(cfg.get("request_timeout") or 90),
            max_retries=int(cfg.get("max_retries") or 3),
            request_delay=cfg.get("request_delay"),
        )
        rows = self._parse_virtual_rows(html, list_url=list_url, year=year)
        max_items = int(cfg.get("max_items") or 0)
        if max_items > 0:
            rows = rows[:max_items]

        concurrency = int(cfg.get("detail_concurrency") or 2)
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_detail(row: dict[str, str]) -> tuple[dict[str, str], dict[str, Any]]:
            async with semaphore:
                try:
                    detail_html = await fetch_page(
                        row["href"],
                        timeout=float(cfg.get("request_timeout") or 90),
                        max_retries=int(cfg.get("max_retries") or 3),
                        request_delay=cfg.get("request_delay"),
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[%s] failed CVF virtual detail %s: %s",
                        self.source_id,
                        row["href"],
                        exc,
                    )
                    return row, {}
                return row, self._parse_virtual_detail(detail_html, fallback_title=row["title"])

        details = await asyncio.gather(*(fetch_detail(row) for row in rows))
        now = datetime.now(timezone.utc)
        items: list[CrawledItem] = []
        for row, detail in details:
            title = str(detail.get("title") or row["title"]).strip()
            if not title:
                continue
            authors_list = [
                str(author).strip()
                for author in detail.get("authors") or []
                if str(author).strip()
            ]
            raw_id = f"{venue}{year}/{row['poster_id']}"
            paper_id = f"cvf_virtual:{raw_id}"
            authors_data = [
                {
                    "paper_id": paper_id,
                    "author_order": idx + 1,
                    "name_raw": author,
                    "name_normalized": author,
                    "source_author_id": None,
                    "author_url": None,
                    "affiliation": None,
                    "affiliation_country": None,
                    "email": None,
                    "orcid": None,
                    "scraped_at": now.isoformat(),
                    "schema_version": "1.0",
                }
                for idx, author in enumerate(authors_list)
            ]
            track_label = cfg.get("track_label", "Main Conference")
            published_at = _parse_virtual_date(detail.get("publication_date"), fallback_year=year)
            paper_data = {
                "paper_id": paper_id,
                "source": "cvf_virtual",
                "raw_id": raw_id,
                "venue": venue,
                "venue_full": cfg.get("venue_full") or _VENUE_FULL.get(venue, venue),
                "year": year,
                "track": track_label,
                "is_main_track": cfg.get("is_main_track", True),
                "is_workshop": cfg.get("is_workshop", False),
                "title": title,
                "abstract": detail.get("abstract"),
                "n_authors": len(authors_list),
                "url": row["href"],
                "pdf_url": None,
                "doi": None,
                "arxiv_id": None,
                "scraped_at": now.isoformat(),
                "schema_version": "1.0",
            }
            items.append(
                CrawledItem(
                    title=title,
                    url=row["href"],
                    published_at=published_at,
                    author=authors_list[0] if authors_list else None,
                    content=paper_data["abstract"],
                    source_id=self.source_id,
                    dimension=cfg.get("dimension", "academic_venues"),
                    tags=[venue, str(year), track_label],
                    extra={"paper": paper_data, "authors": authors_data},
                )
            )
        return items

    @staticmethod
    def _absolutize(href: str) -> str:
        if href.startswith("http"):
            return href
        return f"{BASE}/{href.lstrip('/')}"

    @classmethod
    def _parse_rows(cls, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        rows: list[dict[str, Any]] = []
        for dt in soup.select("dt.ptitle"):
            if not isinstance(dt, Tag):
                continue
            link = dt.find("a", href=True)
            if link is None:
                continue
            href = str(link.get("href") or "").strip()
            title = link.get_text(" ", strip=True)
            if not href or not title:
                continue

            authors_dd = dt.find_next_sibling("dd")
            links_dd = authors_dd.find_next_sibling("dd") if isinstance(authors_dd, Tag) else None
            author_links = authors_dd.select("a") if isinstance(authors_dd, Tag) else []
            if author_links:
                authors = [
                    a.get_text(" ", strip=True)
                    for a in author_links
                    if a.get_text(" ", strip=True)
                ]
            else:
                author_text = (
                    authors_dd.get_text(", ", strip=True)
                    if isinstance(authors_dd, Tag)
                    else ""
                )
                authors = [token.strip() for token in author_text.split(",") if token.strip()]

            link_hrefs = []
            if isinstance(links_dd, Tag):
                for anchor in links_dd.select("a[href]"):
                    href_value = str(anchor.get("href") or "").strip()
                    if href_value:
                        link_hrefs.append(href_value)

            rows.append(
                {
                    "href": href.lstrip("/"),
                    "title": title,
                    "authors": authors,
                    "link_hrefs": link_hrefs,
                }
            )
        return rows

    @staticmethod
    def _parse_virtual_rows(html: str, *, list_url: str, year: int) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        poster_re = re.compile(rf"/virtual/{year}/poster/(\d+)")
        for anchor in soup.select("a[href]"):
            href = str(anchor.get("href") or "").strip()
            match = poster_re.fullmatch(href) or poster_re.search(href)
            if not match:
                continue
            detail_url = urljoin(list_url, match.group(0))
            if detail_url in seen:
                continue
            title = anchor.get_text(" ", strip=True)
            if not title:
                continue
            seen.add(detail_url)
            rows.append({"href": detail_url, "title": title, "poster_id": match.group(1)})
        return rows

    @staticmethod
    def _parse_virtual_detail(html: str, *, fallback_title: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        title = fallback_title
        authors: list[str] = []
        publication_date: str | None = None
        for script in soup.select('script[type="application/ld+json"]'):
            raw = script.string or script.get_text("", strip=True)
            if not raw.strip():
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            records = payload if isinstance(payload, list) else [payload]
            for record in records:
                if not isinstance(record, dict):
                    continue
                title = str(record.get("name") or title).strip()
                publication_date = (
                    str(record.get("datePublished") or "").strip() or publication_date
                )
                raw_authors = record.get("author")
                if isinstance(raw_authors, list):
                    authors = [
                        str(item.get("name") if isinstance(item, dict) else item).strip()
                        for item in raw_authors
                        if str(item.get("name") if isinstance(item, dict) else item).strip()
                    ]
        if not authors:
            organizers = soup.select_one(".event-organizers")
            if organizers is not None:
                authors = [
                    token.strip()
                    for token in re.split(r"\s*[⋅·]\s*", organizers.get_text(" ", strip=True))
                    if token.strip()
                ]
        abstract_el = soup.select_one(".abstract-text-inner")
        abstract = abstract_el.get_text(" ", strip=True) if abstract_el else None
        title_el = soup.select_one(".event-title")
        if title_el is not None:
            title = title_el.get_text(" ", strip=True) or title
        return {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "publication_date": publication_date,
        }


_VENUE_FULL = {
    "CVPR": "IEEE/CVF Conference on Computer Vision and Pattern Recognition",
    "ICCV": "IEEE/CVF International Conference on Computer Vision",
    "WACV": "IEEE/CVF Winter Conference on Applications of Computer Vision",
}


def _parse_virtual_date(value: Any, *, fallback_year: int) -> datetime:
    text = str(value or "").strip()
    if text:
        try:
            parsed = datetime.fromisoformat(text)
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        except ValueError:
            pass
    return datetime(fallback_year, 6, 1, tzinfo=timezone.utc)
