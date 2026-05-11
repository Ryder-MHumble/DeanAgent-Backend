from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.crawlers.registry import CrawlerRegistry
from app.crawlers.utils.json_storage import save_crawl_result_json
from app.db.pool import get_pool
from app.scheduler.manager import load_all_source_configs
from app.schemas.paper import (
    PaperCrawlResponse,
    PaperIngestRunListResponse,
    PaperListResponse,
    PaperRecord,
    PaperSourceListResponse,
    PaperSourceStatus,
)
from app.services import paper_service

router = APIRouter()


def _get_pool_or_none():
    try:
        return get_pool()
    except RuntimeError:
        return None


def _paper_source_configs() -> list[dict]:
    return [
        cfg
        for cfg in load_all_source_configs()
        if cfg.get("dimension") == "paper" and cfg.get("entity_family") == "paper_record"
    ]


async def _list_configured_paper_sources() -> list[dict]:
    pool = _get_pool_or_none()
    stats = await paper_service.list_source_stats(pool) if pool is not None else {}
    items = []
    for cfg in _paper_source_configs():
        stat = stats.get(cfg["id"], {})
        items.append(
            PaperSourceStatus(
                source_id=cfg["id"],
                name=cfg.get("name", cfg["id"]),
                source_type=str(cfg.get("source_type") or "raw_official"),
                crawler_class=str(cfg.get("crawler_class") or ""),
                is_enabled=bool(cfg.get("is_enabled", False)),
                paper_count=int(stat.get("paper_count") or 0),
                latest_run=stat.get("latest_run"),
            ).model_dump(mode="json")
        )
    return items


async def _crawl_paper_source(source_id: str) -> dict:
    config = next((cfg for cfg in _paper_source_configs() if cfg["id"] == source_id), None)
    if config is None:
        raise HTTPException(status_code=404, detail="paper source not found")
    crawler = CrawlerRegistry.create_crawler(config)
    result = await crawler.run()
    save_summary = await save_crawl_result_json(result, config)
    pool = _get_pool_or_none()
    if pool is None:
        latest = {}
    else:
        runs = await paper_service.list_import_runs(pool, source_id=source_id, page=1, page_size=1)
        latest = runs["items"][0] if runs["items"] else {}
    return PaperCrawlResponse(
        source_id=source_id,
        status=result.status.value,
        inserted_count=save_summary["new"],
        updated_count=max(save_summary["upserted"] - save_summary["new"], 0),
        skipped_count=0,
        filtered_chinese_count=int(latest.get("filtered_chinese_count") or 0),
        run_id=latest.get("run_id"),
        error_message=result.error_message,
    ).model_dump(mode="json")


@router.get(
    "/papers",
    response_model=PaperListResponse,
    summary="全局论文列表",
)
async def list_papers(
    q: str | None = Query(default=None),
    doi: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    source_name: str | None = Query(default=None),
    source_id: str | None = Query(default=None),
    venue: str | None = Query(default=None),
    venue_year: int | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    affiliation: str | None = Query(default=None, description="Filter by affiliation text (ILIKE match on affiliations JSONB)"),
    has_abstract: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="publication_date"),
    order: str = Query(default="desc"),
) -> PaperListResponse:
    payload = await paper_service.list_papers(
        _get_pool_or_none(),
        q=q,
        doi=doi,
        source_type=source_type,
        source_name=source_name,
        source_id=source_id,
        venue=venue,
        venue_year=venue_year,
        date_from=date_from,
        date_to=date_to,
        affiliation=affiliation,
        has_abstract=has_abstract,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        order=order,
    )
    return PaperListResponse(**payload)


@router.get(
    "/papers/sources",
    response_model=PaperSourceListResponse,
    summary="论文仓信源列表",
)
async def list_paper_sources() -> PaperSourceListResponse:
    items = await _list_configured_paper_sources()
    return PaperSourceListResponse(items=[PaperSourceStatus(**item) for item in items], total=len(items))


@router.post(
    "/papers/sources/{source_id}/crawl",
    response_model=PaperCrawlResponse,
    summary="触发单个论文仓信源抓取",
)
async def crawl_paper_source(source_id: str) -> PaperCrawlResponse:
    payload = await _crawl_paper_source(source_id)
    return PaperCrawlResponse(**payload)


@router.get(
    "/papers/import-runs",
    response_model=PaperIngestRunListResponse,
    summary="论文仓导入运行记录",
)
async def list_paper_import_runs(
    source_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaperIngestRunListResponse:
    payload = await paper_service.list_import_runs(
        _get_pool_or_none(),
        source_id=source_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return PaperIngestRunListResponse(**payload)


@router.get(
    "/papers/{paper_id}",
    response_model=PaperRecord,
    summary="全局论文详情",
)
async def get_paper(paper_id: str) -> PaperRecord:
    record = await paper_service.get_paper(_get_pool_or_none(), paper_id)
    if record is None:
        raise HTTPException(status_code=404, detail="paper not found")
    return PaperRecord(**record)
