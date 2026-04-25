from __future__ import annotations

import pytest

from app.crawlers.parsers.zhejianglab_website_api import ZhejiangLabWebsiteAPICrawler


@pytest.mark.asyncio
async def test_zhejianglab_website_api_crawler_parses_records(monkeypatch: pytest.MonkeyPatch):
    async def fake_fetch_json(*_args, **kwargs):
        module_id = int(kwargs["params"]["moudleId"])
        if module_id == 527:
            return {"data": []}
        return {
            "data": [
                {
                    "columnName": "之江要闻",
                    "data": [
                        {
                            "id": 3768,
                            "title": "之江实验室召开2026年全面从严治党会议",
                            "publishTime": "2026-03-26 17:18:11",
                            "createdBy": "zjadmin",
                            "introduce": "<p>示例正文</p>",
                            "originalContent": "示例正文",
                            "outerUrl": "",
                        },
                        {
                            "id": 3765,
                            "title": "之江实验室党委传达学习习近平总书记重要讲话和全国两会精神",
                            "publishTime": "2026-03-23 09:14:20",
                            "createdBy": "zjadmin",
                            "introduce": "<p>第二篇</p>",
                            "originalContent": "第二篇",
                            "outerUrl": "",
                        },
                    ],
                }
            ]
        }

    monkeypatch.setattr(
        "app.crawlers.parsers.zhejianglab_website_api.fetch_json",
        fake_fetch_json,
    )

    crawler = ZhejiangLabWebsiteAPICrawler(
        {
            "id": "zhejianglab_news",
            "name": "之江实验室",
            "dimension": "universities",
            "tags": ["institute", "zhejianglab", "ai"],
            "module_ids": [515, 527],
            "max_items": 12,
        }
    )

    items = await crawler.fetch_and_parse()

    assert len(items) == 2
    assert items[0].title == "之江实验室召开2026年全面从严治党会议"
    assert items[0].url == "https://www.zhejianglab.org/lab/post/3768"
    assert items[0].published_at is not None
    assert items[0].published_at.year == 2026
    assert items[0].content == "示例正文"
    assert items[0].extra["column_name"] == "之江要闻"
