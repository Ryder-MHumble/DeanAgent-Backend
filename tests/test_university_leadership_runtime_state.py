from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.crawlers.base import CrawlResult, CrawlStatus, CrawledItem
from app.services.core.institution import leadership


SOURCE_CONFIG = {
    "id": "leaders_demo",
    "name": "示例大学-现任领导(官方)",
    "url": "https://example.com/leaders",
    "dimension": "personnel",
    "group": "university_leadership_official",
    "crawl_method": "university_leadership",
    "is_enabled": True,
}


@pytest.mark.asyncio
async def test_run_university_leadership_full_crawl_records_success_runtime_state():
    started_at = datetime(2026, 4, 8, 8, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 4, 8, 8, 1, tzinfo=timezone.utc)
    result = CrawlResult(
        source_id=SOURCE_CONFIG["id"],
        status=CrawlStatus.SUCCESS,
        items=[],
        items_all=[
            CrawledItem(
                title="示例大学现任领导",
                url="https://example.com/leaders/1",
                extra={"name": "张三", "role": "校长"},
            )
        ],
        items_total=1,
        items_new=1,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=60.0,
    )

    crawler = AsyncMock()
    crawler.run.return_value = result

    with (
        patch.object(leadership, "_ensure_tables", AsyncMock()),
        patch.object(leadership, "_load_institution_name_map", AsyncMock(return_value={})),
        patch.object(leadership, "load_all_source_configs", return_value=[SOURCE_CONFIG]),
        patch.object(leadership.CrawlerRegistry, "create_crawler", return_value=crawler),
        patch.object(leadership, "save_crawl_result_json", AsyncMock()),
        patch.object(leadership, "_upsert_current", AsyncMock(return_value={"changed": False})),
        patch.object(leadership, "append_crawl_log", AsyncMock()) as append_log,
        patch.object(leadership, "update_source_state", AsyncMock()) as update_state,
    ):
        summary = await leadership.run_university_leadership_full_crawl()

    assert summary["success_sources"] == 1
    append_log.assert_awaited_once()
    _, kwargs = append_log.await_args
    assert kwargs["source_id"] == SOURCE_CONFIG["id"]
    assert kwargs["status"] == CrawlStatus.SUCCESS.value
    assert kwargs["items_total"] == 1
    assert kwargs["items_new"] == 1
    update_state.assert_awaited_once_with(
        SOURCE_CONFIG["id"],
        last_crawl_at=finished_at,
        last_success_at=finished_at,
        reset_failures=True,
    )


@pytest.mark.asyncio
async def test_run_university_leadership_full_crawl_records_failed_runtime_state_on_create_error():
    started_at = datetime(2026, 4, 8, 9, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return started_at if tz else started_at.replace(tzinfo=None)

    with (
        patch.object(leadership, "_ensure_tables", AsyncMock()),
        patch.object(leadership, "_load_institution_name_map", AsyncMock(return_value={})),
        patch.object(leadership, "load_all_source_configs", return_value=[SOURCE_CONFIG]),
        patch.object(
            leadership.CrawlerRegistry,
            "create_crawler",
            side_effect=RuntimeError("boom"),
        ),
        patch.object(leadership, "append_crawl_log", AsyncMock()) as append_log,
        patch.object(leadership, "update_source_state", AsyncMock()) as update_state,
        patch.object(leadership, "datetime", FixedDateTime),
    ):
        summary = await leadership.run_university_leadership_full_crawl()

    assert summary["failed_sources"] == 1
    append_log.assert_awaited_once()
    _, kwargs = append_log.await_args
    assert kwargs["source_id"] == SOURCE_CONFIG["id"]
    assert kwargs["status"] == CrawlStatus.FAILED.value
    assert "create crawler failed" in kwargs["error_message"]
    update_state.assert_awaited_once_with(
        SOURCE_CONFIG["id"],
        last_crawl_at=started_at,
    )
