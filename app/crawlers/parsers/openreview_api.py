"""OpenReview API 爬虫 — api2.openreview.net

覆盖：ICLR / ICML / NeurIPS（2023+）+ 各 workshop
数据源：OpenReview API v2
特点：
- JSON API，支持大批量拉取
- 带 venueid + primary_area + keywords 等细粒度字段
- 接受/拒稿/撤稿状态可过滤

Venue ID 映射（YAML 里配置）：
    ICLR.cc/2024/Conference       → ICLR 2024 主会
    ICML.cc/2024/Conference       → ICML 2024
    NeurIPS.cc/2024/Conference    → NeurIPS 2024
    ICLR.cc/2024/Workshop/XXX     → workshop

⚠️ 限流：匿名 ~100 req/min。爬 note 列表用一次分页 API 即可（每页 1000 篇），
   所以一个 venue 只需 ~5-10 个 API 请求，极少触发限流。
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from app.crawlers.base import BaseCrawler, CrawledItem
    from app.crawlers.utils.http_client import fetch_page
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from base import BaseCrawler, CrawledItem  # type: ignore

    async def fetch_page(url: str, timeout: float = 30.0, max_retries: int = 3) -> str:
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
                    # 429 退避更久
                    delay = 30 if "429" in str(e) else (2 ** attempt)
                    await asyncio.sleep(delay)
        raise last_err


logger = logging.getLogger(__name__)


class OpenReviewCrawler(BaseCrawler):
    """OpenReview venue 论文抓取。

    YAML 字段：
        id: iclr-2024
        crawler_class: openreview
        venue: ICLR
        year: 2024
        venue_id: ICLR.cc/2024/Conference       # OpenReview 系统内的 venue 标识
        api_version: 2                           # 1 或 2，默认 2
        track_label: Main Conference             # 展示名
        is_main_track: true
        is_workshop: false
        page_size: 1000                          # 每次请求论文数
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
        venue: str = cfg["venue"]
        year: int = int(cfg["year"])
        venue_id: str = cfg["venue_id"]
        api_version: int = int(cfg.get("api_version", 2))
        track_label: str = cfg.get("track_label", "Main Conference")
        is_main_track: bool = cfg.get("is_main_track", True)
        is_workshop: bool = cfg.get("is_workshop", False)
        page_size: int = int(cfg.get("page_size", 1000))

        api_host = "https://api2.openreview.net" if api_version == 2 else "https://api.openreview.net"

        # 翻页抓所有 notes
        all_notes: list[dict] = []
        offset = 0
        while True:
            url = (f"{api_host}/notes?"
                   f"content.venueid={venue_id}"
                   f"&limit={page_size}&offset={offset}")
            logger.info(f"[{self.source_id}] fetching offset={offset}")
            raw = await fetch_page(url, timeout=30.0, max_retries=4)
            data = json.loads(raw)
            notes = data.get("notes", [])
            if not notes:
                break
            all_notes.extend(notes)
            if len(notes) < page_size:
                break
            offset += page_size
            await asyncio.sleep(0.6)  # 礼貌间隔

        logger.info(f"[{self.source_id}] fetched {len(all_notes)} notes")

        now = datetime.now(timezone.utc)
        items: list[CrawledItem] = []

        for note in all_notes:
            try:
                item = self._note_to_item(
                    note, venue, year, venue_id, track_label,
                    is_main_track, is_workshop, api_version, now, cfg
                )
                if item:
                    items.append(item)
            except Exception as e:
                logger.warning(f"  ⚠️ parse note {note.get('id')}: {e}")

        return items

    @staticmethod
    def _note_to_item(
        note: dict, venue: str, year: int, venue_id: str,
        track_label: str, is_main_track: bool, is_workshop: bool,
        api_version: int, now: datetime, cfg: dict,
    ) -> CrawledItem | None:
        """Convert OpenReview note JSON → CrawledItem."""

        def g(field: str):
            """API v2 的字段都包在 {value: X}，v1 直接拿。"""
            c = note.get("content", {})
            if api_version == 2:
                v = c.get(field) or {}
                return v.get("value") if isinstance(v, dict) else v
            return c.get(field)

        forum_id = note.get("forum") or note.get("id")
        title = g("title")
        if not title:
            return None
        title = str(title).strip()

        authors = g("authors") or []
        author_ids = g("authorids") or []
        # 规范化：authors 可能是逗号字符串
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",") if a.strip()]

        abstract = g("abstract") or ""
        keywords = g("keywords") or []
        primary_area = g("primary_area") or None
        pdf_path = g("pdf") or None

        paper_id = f"openreview:{forum_id}"
        detail_url = f"https://openreview.net/forum?id={forum_id}"
        pdf_url = f"https://openreview.net/pdf?id={forum_id}" if pdf_path else None

        authors_data = []
        for idx, (name, aid) in enumerate(zip(authors, author_ids or [None] * len(authors))):
            authors_data.append({
                "paper_id": paper_id,
                "author_order": idx + 1,
                "name_raw": name,
                "name_normalized": name,
                "source_author_id": aid,  # OpenReview profile id 如 ~Zhang_Wei1
                "author_url": f"https://openreview.net/profile?id={aid}" if aid else None,
                "affiliation": None,
                "affiliation_country": None,
                "email": None,
                "orcid": None,
                "scraped_at": now.isoformat(),
                "schema_version": "1.0",
            })

        paper_data = {
            "paper_id": paper_id,
            "source": "openreview",
            "raw_id": forum_id,
            "venue": venue,
            "venue_full": cfg.get("venue_full"),
            "year": year,
            "track": track_label,
            "is_main_track": is_main_track,
            "is_workshop": is_workshop,
            "title": title,
            "abstract": str(abstract).strip() if abstract else None,
            "n_authors": len(authors),
            "url": detail_url,
            "pdf_url": pdf_url,
            "doi": None,
            "arxiv_id": None,
            "scraped_at": now.isoformat(),
            "schema_version": "1.0",
        }

        return CrawledItem(
            title=title,
            url=detail_url,
            published_at=datetime(year, 5, 1, tzinfo=timezone.utc),
            author=authors[0] if authors else None,
            source_id=cfg["id"],
            dimension=cfg.get("dimension", "academic_venues"),
            tags=[venue, str(year), track_label]
                 + (keywords if isinstance(keywords, list) else []),
            extra={
                "paper": paper_data,
                "authors": authors_data,
                "primary_area": primary_area,
                "keywords": keywords,
            },
        )
