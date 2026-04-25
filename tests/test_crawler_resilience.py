from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.crawlers.base import CrawledItem
from app.crawlers.parsers.university_news_auto import UniversityNewsAutoCrawler
from app.crawlers.templates.dynamic_crawler import DynamicPageCrawler
from app.crawlers.utils import json_storage
from app.crawlers.utils.selector_parser import parse_list_items


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeArticlesTable:
    def __init__(self) -> None:
        self._selected = False
        self.upsert_rows = None

    def select(self, *_args, **_kwargs):
        self._selected = True
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def upsert(self, rows, **_kwargs):
        self.upsert_rows = rows
        self._selected = False
        return self

    async def execute(self):
        if self._selected:
            return _FakeResponse([])

        for row in self.upsert_rows or []:
            if any(not isinstance(tag, str) for tag in row.get("tags", [])):
                raise TypeError("invalid array element: expected str")
        return _FakeResponse(self.upsert_rows or [])


class _FakeClient:
    def __init__(self) -> None:
        self.articles = _FakeArticlesTable()

    def table(self, name: str):
        assert name == "articles"
        return self.articles


class _FakePage:
    def __init__(self, html: str) -> None:
        self.html = html

    async def goto(self, *_args, **_kwargs):
        return None

    async def wait_for_selector(self, *_args, **_kwargs):
        raise RuntimeError("timeout waiting for selector")

    async def content(self):
        return self.html


def test_parse_list_items_reads_english_month_dates():
    html = """
    <div class="grid">
      <a class="group" href="news/introducing-runway-fund">
        <div class="text-2xl">Introducing Runway Fund</div>
        <div class="mt-1">Alejandro Matamala Ortiz / March 31, 2026</div>
      </a>
    </div>
    """

    items = parse_list_items(
        __import__("bs4").BeautifulSoup(html, "lxml"),
        {
            "list_item": "a.group[href^='news/']",
            "title": "div.text-2xl",
            "link": "_self",
            "date": "div.mt-1",
        },
        "https://runwayml.com/",
    )

    assert len(items) == 1
    assert items[0].published_at is not None
    assert items[0].published_at.year == 2026
    assert items[0].published_at.month == 3
    assert items[0].published_at.day == 31


@pytest.mark.asyncio
async def test_save_crawl_result_json_coerces_mixed_tags_to_strings(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_client = _FakeClient()
    monkeypatch.setattr("app.db.client.get_client", lambda: fake_client)

    result = SimpleNamespace(
        items=[
            CrawledItem(
                title="南开大学示例",
                url="https://news.nankai.edu.cn/ywsd/system/2026/04/23/030071554.shtml",
                tags=["university", 985, "auto", "nankai"],
                source_id="nankai_news_auto",
                dimension="universities",
            )
        ]
    )

    persisted = await json_storage.save_crawl_result_json(
        result,
        {"id": "nankai_news_auto", "group": "university_news", "dimension": "universities"},
    )

    assert persisted["upserted"] == 1
    assert fake_client.articles.upsert_rows[0]["tags"] == ["university", "985", "auto", "nankai"]


@pytest.mark.asyncio
async def test_save_crawl_result_json_skips_when_persistence_disabled(
    monkeypatch: pytest.MonkeyPatch,
):
    called = False

    def fail_get_client():
        nonlocal called
        called = True
        raise RuntimeError("DB client should not be touched")

    monkeypatch.setattr("app.db.client.get_client", fail_get_client)

    result = SimpleNamespace(
        items=[
            CrawledItem(
                title="天池示例",
                url="https://tianchi.aliyun.com/competition/entrance/532406/rankRange",
                source_id="aliyun_tianchi",
                dimension="talent_scout",
            )
        ]
    )

    persisted = await json_storage.save_crawl_result_json(
        result,
        {
            "id": "aliyun_tianchi",
            "group": "talent_competitions",
            "dimension": "talent_scout",
            "persist_to_db": False,
        },
    )

    assert persisted == {"upserted": 0, "new": 0, "deduped_in_batch": 0}
    assert called is False


@pytest.mark.asyncio
async def test_dynamic_page_crawler_uses_current_html_when_wait_times_out(
    monkeypatch: pytest.MonkeyPatch,
):
    html = """
    <html>
      <body>
        <div class="news-list">
          <ul>
            <li><a href="/article/1">南开大学示例新闻</a></li>
          </ul>
        </div>
      </body>
    </html>
    """

    @asynccontextmanager
    async def fake_get_page(**_kwargs):
        yield _FakePage(html)

    monkeypatch.setattr("app.crawlers.utils.playwright_pool.get_page", fake_get_page)

    crawler = DynamicPageCrawler(
        {
            "id": "nankai_news",
            "url": "https://news.nankai.edu.cn/",
            "base_url": "https://news.nankai.edu.cn/",
            "wait_for": "div.right_con",
            "wait_timeout": 15000,
            "selectors": {
                "list_item": "div.news-list ul li",
                "title": "a",
                "link": "a",
            },
            "tags": ["university", "nankai", "news"],
        }
    )

    items = await crawler.fetch_and_parse()

    assert len(items) == 1
    assert items[0].title == "南开大学示例新闻"
    assert items[0].url == "https://news.nankai.edu.cn/article/1"


@pytest.mark.asyncio
async def test_university_news_auto_backfills_published_at_from_detail(
    monkeypatch: pytest.MonkeyPatch,
):
    list_html = """
    <html>
      <body>
        <a href="/info/1002/230332.htm">西安交通大学示例新闻标题</a>
      </body>
    </html>
    """
    detail_html = """
    <html>
      <body>
        <div class="article">正文内容</div>
        <div>发布时间：2026-03-28 10:29</div>
      </body>
    </html>
    """

    async def fake_fetch_page(url: str, **_kwargs):
        if url == "https://news.example.edu/":
            return list_html
        if url == "https://news.example.edu/info/1002/230332.htm":
            return detail_html
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(
        "app.crawlers.parsers.university_news_auto.fetch_page",
        fake_fetch_page,
    )

    crawler = UniversityNewsAutoCrawler(
        {
            "id": "xjtu_news_auto",
            "url": "https://news.example.edu/",
            "base_url": "https://news.example.edu/",
            "fetch_detail": True,
            "playwright_fallback": False,
            "max_items": 10,
            "detail_max_items": 3,
            "detail_min_length": 1,
            "tags": ["university", "xjtu", "news"],
        }
    )

    items = await crawler.fetch_and_parse()

    assert len(items) == 1
    assert items[0].published_at is not None
    assert items[0].published_at.year == 2026
    assert items[0].published_at.month == 3
    assert items[0].published_at.day == 28
