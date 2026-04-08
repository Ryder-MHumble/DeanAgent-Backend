from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.crawlers.base import CrawledItem, CrawlResult, CrawlStatus
from app.services.core.institution import leadership


class _DummyCrawler:
    def __init__(self, result: CrawlResult) -> None:
        self._result = result

    async def run(self) -> CrawlResult:
        return self._result


@pytest.mark.asyncio
async def test_run_university_leadership_full_crawl_updates_state_on_success():
    started_at = datetime(2026, 4, 8, 6, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 4, 8, 6, 0, 12, tzinfo=timezone.utc)
    source_config = {
        "id": "leaders_tsinghua",
        "name": "清华大学-现任领导(官方)",
        "url": "https://example.com/leader",
        "crawl_method": "university_leadership",
        "is_enabled": True,
    }
    crawled_item = CrawledItem(
        title="党委书记",
        url="https://example.com/leader/1",
        source_id="leaders_tsinghua",
        extra={"name": "张三", "position": "党委书记"},
    )
    crawl_result = CrawlResult(
        source_id="leaders_tsinghua",
        status=CrawlStatus.SUCCESS,
        items=[crawled_item],
        items_all=[crawled_item],
        items_new=1,
        items_total=1,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=12.0,
    )

    with (
        patch.object(leadership, "_ensure_tables", new=AsyncMock()),
        patch.object(leadership, "load_all_source_configs", return_value=[source_config]),
        patch.object(
            leadership,
            "_load_institution_name_map",
            new=AsyncMock(return_value={"清华大学": "inst-1"}),
        ),
        patch.object(
            leadership.CrawlerRegistry,
            "create_crawler",
            return_value=_DummyCrawler(crawl_result),
        ),
        patch.object(leadership, "save_crawl_result_json", new=AsyncMock()),
        patch.object(
            leadership,
            "_upsert_current",
            new=AsyncMock(
                return_value={
                    "changed": True,
                    "new_leader_count": 1,
                    "change_version": 2,
                }
            ),
        ),
        patch.object(leadership, "append_crawl_log", new=AsyncMock()) as append_log,
        patch.object(leadership, "update_source_state", new=AsyncMock()) as update_state,
    ):
        summary = await leadership.run_university_leadership_full_crawl(max_concurrency=1)

    assert summary["total_sources"] == 1
    assert summary["success_sources"] == 1
    assert summary["failed_sources"] == 0
    append_log.assert_awaited_once_with(
        source_id="leaders_tsinghua",
        status="success",
        items_total=1,
        items_new=1,
        error_message=None,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=12.0,
    )
    update_state.assert_awaited_once_with(
        "leaders_tsinghua",
        last_crawl_at=finished_at,
        last_success_at=finished_at,
        reset_failures=True,
    )


@pytest.mark.asyncio
async def test_run_university_leadership_full_crawl_updates_state_on_failure():
    started_at = datetime(2026, 4, 8, 6, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 4, 8, 6, 0, 5, tzinfo=timezone.utc)
    source_config = {
        "id": "leaders_tsinghua",
        "name": "清华大学-现任领导(官方)",
        "url": "https://example.com/leader",
        "crawl_method": "university_leadership",
        "is_enabled": True,
    }
    crawl_result = CrawlResult(
        source_id="leaders_tsinghua",
        status=CrawlStatus.FAILED,
        error_message="network error",
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=5.0,
    )

    with (
        patch.object(leadership, "_ensure_tables", new=AsyncMock()),
        patch.object(leadership, "load_all_source_configs", return_value=[source_config]),
        patch.object(leadership, "_load_institution_name_map", new=AsyncMock(return_value={})),
        patch.object(
            leadership.CrawlerRegistry,
            "create_crawler",
            return_value=_DummyCrawler(crawl_result),
        ),
        patch.object(leadership, "save_crawl_result_json", new=AsyncMock()),
        patch.object(leadership, "_upsert_current", new=AsyncMock()),
        patch.object(leadership, "append_crawl_log", new=AsyncMock()) as append_log,
        patch.object(leadership, "update_source_state", new=AsyncMock()) as update_state,
    ):
        summary = await leadership.run_university_leadership_full_crawl(max_concurrency=1)

    assert summary["total_sources"] == 1
    assert summary["success_sources"] == 0
    assert summary["failed_sources"] == 1
    append_log.assert_awaited_once_with(
        source_id="leaders_tsinghua",
        status="failed",
        items_total=0,
        items_new=0,
        error_message="network error",
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=5.0,
    )
    update_state.assert_awaited_once_with(
        "leaders_tsinghua",
        last_crawl_at=finished_at,
    )
