from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from app.crawlers.registry import CrawlerRegistry
from app.crawlers.utils.json_storage import save_crawl_result_json
from app.crawlers.utils.http_client import fetch_page
from app.db.client import get_client
from app.scheduler.manager import load_all_source_configs
from app.services.intel.pipeline.university_eco_processor import (
    process_university_eco_pipeline,
)
from app.utils.date_parsing import (
    extract_datetime_from_html,
    extract_datetime_from_text,
    extract_datetime_from_url,
)


@dataclass(slots=True)
class BackfillResult:
    source_id: str
    status: str
    missing_before: int
    missing_after: int
    rows_attempted: int = 0
    rows_backfilled: int = 0
    items_total: int = 0
    items_new: int = 0
    upserted: int = 0
    new_rows: int = 0
    error: str | None = None


def summarize_missing_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        source_id = str(row.get("source_id") or "").strip()
        if not source_id:
            continue
        if row.get("published_at") is None:
            counter[source_id] += 1
    return dict(counter)


def pick_target_source_ids(
    counts: dict[str, int],
    *,
    requested: list[str] | None = None,
    limit: int | None = None,
) -> list[str]:
    if requested:
        deduped: list[str] = []
        seen: set[str] = set()
        for source_id in requested:
            if source_id in counts and source_id not in seen:
                seen.add(source_id)
                deduped.append(source_id)
        return deduped

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    source_ids = [source_id for source_id, count in ranked if count > 0]
    if limit is not None:
        return source_ids[: max(0, limit)]
    return source_ids


async def fetch_missing_published_at_rows() -> list[dict[str, Any]]:
    client = get_client()
    res = await client.table("articles").select("source_id,published_at").eq(
        "dimension", "universities"
    ).execute()
    return res.data or []


async def count_missing_published_at_by_source() -> dict[str, int]:
    return summarize_missing_counts(await fetch_missing_published_at_rows())


async def _fetch_source_missing_rows(source_id: str) -> list[dict[str, Any]]:
    client = get_client()
    rows: list[dict[str, Any]] = []
    start = 0
    page_size = 200

    while True:
        res = await client.table("articles").select(
            "url_hash,source_id,url,title,published_at"
        ).eq("dimension", "universities").eq("source_id", source_id).eq(
            "published_at", None
        ).range(start, start + page_size - 1).execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size

    return rows


async def _update_article_published_at(url_hash: str, published_at: str) -> None:
    client = get_client()
    await client.table("articles").update({"published_at": published_at}).eq(
        "url_hash", url_hash
    ).execute()


async def _infer_missing_published_at(
    row: dict[str, Any],
    config: dict[str, Any],
) -> str | None:
    inferred = (
        extract_datetime_from_text(row.get("title"))
        or extract_datetime_from_url(row.get("url"))
    )
    if inferred is not None:
        return inferred.isoformat()

    html = await fetch_page(
        row.get("url", ""),
        headers=config.get("headers"),
        encoding=config.get("encoding"),
        request_delay=0,
    )
    inferred = extract_datetime_from_html(html, require_hint=True)
    if inferred is None:
        return None
    return inferred.isoformat()


async def _backfill_existing_rows_for_source(source_id: str, config: dict[str, Any]) -> tuple[int, int]:
    rows = await _fetch_source_missing_rows(source_id)
    backfilled = 0

    for row in rows:
        try:
            published_at = await _infer_missing_published_at(row, config)
        except Exception:  # noqa: BLE001
            continue
        if not published_at:
            continue
        await _update_article_published_at(str(row.get("url_hash") or ""), published_at)
        backfilled += 1

    return len(rows), backfilled


async def execute_university_published_at_backfill(
    *,
    requested_sources: list[str] | None = None,
    limit: int | None = None,
    rebuild_outputs: bool = True,
) -> dict[str, Any]:
    before_counts = await count_missing_published_at_by_source()
    target_source_ids = pick_target_source_ids(
        before_counts,
        requested=requested_sources,
        limit=limit,
    )

    config_by_source = {
        str(config.get("id") or ""): config
        for config in load_all_source_configs()
        if config.get("dimension") == "universities"
    }

    results: list[BackfillResult] = []
    for source_id in target_source_ids:
        config = config_by_source.get(source_id)
        if not config:
            results.append(
                BackfillResult(
                    source_id=source_id,
                    status="missing_config",
                    missing_before=before_counts.get(source_id, 0),
                    missing_after=before_counts.get(source_id, 0),
                    error=f"Source config not found: {source_id}",
                )
            )
            continue

        try:
            rows_attempted, rows_backfilled = await _backfill_existing_rows_for_source(
                source_id, config
            )
            crawler = CrawlerRegistry.create_crawler(config)
            crawl_result = await crawler.run()
            persist_result = await save_crawl_result_json(crawl_result, config)
            results.append(
                BackfillResult(
                    source_id=source_id,
                    status=crawl_result.status.value,
                    missing_before=before_counts.get(source_id, 0),
                    missing_after=before_counts.get(source_id, 0),
                    rows_attempted=rows_attempted,
                    rows_backfilled=rows_backfilled,
                    items_total=crawl_result.items_total,
                    items_new=crawl_result.items_new,
                    upserted=persist_result.get("upserted", 0),
                    new_rows=persist_result.get("new", 0),
                    error=crawl_result.error_message,
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                BackfillResult(
                    source_id=source_id,
                    status="failed",
                    missing_before=before_counts.get(source_id, 0),
                    missing_after=before_counts.get(source_id, 0),
                    error=str(exc),
                )
            )

    after_counts = await count_missing_published_at_by_source()
    for result in results:
        result.missing_after = after_counts.get(result.source_id, 0)

    pipeline_result: dict[str, Any] | None = None
    if rebuild_outputs:
        pipeline_result = await process_university_eco_pipeline(force=True)

    return {
        "before_counts": before_counts,
        "after_counts": after_counts,
        "target_sources": target_source_ids,
        "results": [asdict(result) for result in results],
        "pipeline": pipeline_result,
    }
