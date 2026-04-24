from __future__ import annotations

from datetime import datetime

from bs4 import BeautifulSoup

from app.crawlers.utils.selector_parser import (
    extract_date_from_url,
    parse_detail_html,
    parse_list_items,
)
from app.utils.date_parsing import extract_datetime_from_html
from app.services.intel.university import service as university_service


def test_parse_list_items_infers_date_without_explicit_date_format():
    html = """
    <ul class="list">
      <li>
        <a class="title" href="/article/1">上海交通大学示例新闻</a>
        <span class="time">2026年04月23日</span>
      </li>
    </ul>
    """
    soup = BeautifulSoup(html, "lxml")

    items = parse_list_items(
        soup,
        {
            "list_item": "li",
            "title": "a.title",
            "link": "a.title",
            "date": "span.time",
        },
        "https://news.sjtu.edu.cn",
    )

    assert len(items) == 1
    assert items[0].published_at == datetime(2026, 4, 23)


def test_extract_date_from_url_supports_additional_university_patterns():
    assert extract_date_from_url(
        "https://news.fudan.edu.cn/2026/0411/c40a148647/page.htm"
    ) == datetime(2026, 4, 11)
    assert extract_date_from_url(
        "https://news.sjtu.edu.cn/jdyw/20260422/210346.html"
    ) == datetime(2026, 4, 22)
    assert extract_date_from_url(
        "https://jyt.jiangsu.gov.cn/art/2026/3/31/art_57813_11752296.html"
    ) == datetime(2026, 3, 31)


def test_parse_list_items_infers_split_day_and_year_month():
    html = """
    <ul class="list">
      <li>
        <a class="title" href="/article/1">国防科技大学示例新闻</a>
        <div class="date">
          <div class="day">17</div>
          <div class="year">2026-04</div>
        </div>
      </li>
    </ul>
    """
    soup = BeautifulSoup(html, "lxml")

    items = parse_list_items(
        soup,
        {
            "list_item": "li",
            "title": "a.title",
            "link": "a.title",
            "date": "div.date",
        },
        "https://www.nudt.edu.cn",
    )

    assert len(items) == 1
    assert items[0].published_at == datetime(2026, 4, 17)


def test_parse_detail_html_extracts_published_at_from_detail_metadata():
    html = """
    <html>
      <body>
        <div class="meta">
          <span>日期：2026-03-28 10:29</span>
        </div>
        <div class="content"><p>正文内容</p></div>
      </body>
    </html>
    """

    detail = parse_detail_html(
        html,
        {"content": "div.content"},
        "https://news.xjtu.edu.cn/info/1002/230332.htm",
    )

    assert detail.published_at == datetime(2026, 3, 28, 10, 29)


def test_extract_datetime_from_html_reads_publishdate_meta():
    html = """
    <html>
      <head>
        <meta name="publishdate" content="2026-03-26 22:49:11" />
      </head>
      <body>
        <div>正文内容</div>
      </body>
    </html>
    """

    assert extract_datetime_from_html(html, require_hint=True) == datetime(
        2026, 3, 26, 22, 49, 11
    )


def test_extract_datetime_from_html_reads_time_tag():
    html = """
    <html>
      <body>
        <time class="times">2025/10/02</time>
      </body>
    </html>
    """

    assert extract_datetime_from_html(html, require_hint=True) == datetime(2025, 10, 2)


def test_extract_datetime_from_html_reads_structured_date_class():
    html = """
    <html>
      <body>
        <div class="aside-time">2025.10 19</div>
      </body>
    </html>
    """

    assert extract_datetime_from_html(html, require_hint=True) == datetime(2025, 10, 19)


def test_extract_datetime_from_html_reads_adjacent_hint_and_date_lines():
    html = """
    <html>
      <body>
        <span>发布日期：</span>
        <a>2026-03-21</a>
      </body>
    </html>
    """

    assert extract_datetime_from_html(html, require_hint=True) == datetime(2026, 3, 21)


async def test_university_feed_backfills_missing_published_at_and_resorts(monkeypatch):
    rows = [
        {
            "url_hash": "xjtu-1",
            "title": "西交大示例",
            "url": "https://news.xjtu.edu.cn/info/1002/230332.htm",
            "published_at": None,
            "source_id": "xjtu_news",
            "source_name": "西安交通大学新闻网-要闻聚焦",
            "group": "university_news",
            "tags": ["university", "xjtu", "news"],
            "content": "正文",
            "content_html": '<div><span>日期：2026-03-28 10:29</span><div class="v_news_content">正文</div></div>',
            "extra": {},
            "is_new": False,
        },
        {
            "url_hash": "fudan-1",
            "title": "复旦示例",
            "url": "https://news.fudan.edu.cn/2026/0411/c40a148647/page.htm",
            "published_at": None,
            "source_id": "fudan_news",
            "source_name": "复旦大学新闻网",
            "group": "university_news",
            "tags": ["university", "fudan", "news"],
            "content": "正文",
            "content_html": '<div><span class="arti_update">发布时间：2026-04-11</span><div class="article">正文</div></div>',
            "extra": {},
            "is_new": False,
        },
    ]

    async def fake_get_articles(*args, **kwargs):
        return list(rows)

    monkeypatch.setattr(university_service, "get_articles", fake_get_articles)
    monkeypatch.setattr(university_service, "filter_university_articles", lambda items: items)
    monkeypatch.setattr(university_service, "dedupe_university_articles", lambda items: items)

    payload = await university_service.get_feed(page=1, page_size=20)

    assert [item["id"] for item in payload["items"]] == ["fudan-1", "xjtu-1"]
    assert payload["items"][0]["published_at"] == "2026-04-11T00:00:00"
    assert payload["items"][1]["published_at"] == "2026-03-28T10:29:00"
