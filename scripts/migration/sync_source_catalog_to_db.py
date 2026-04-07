#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
import yaml

from app.config import BASE_DIR, settings
from app.services.core.source_catalog_meta import build_source_catalog_meta

SCHEDULE_TO_MINUTES: dict[str, int] = {
    "2h": 120,
    "4h": 240,
    "daily": 24 * 60,
    "daily_bj_4": 24 * 60,
    "weekly": 7 * 24 * 60,
    "monthly": 30 * 24 * 60,
}

UNIVERSITY_985: set[str] = {
    "清华大学",
    "北京大学",
    "中国人民大学",
    "北京航空航天大学",
    "北京理工大学",
    "中国农业大学",
    "北京师范大学",
    "中央民族大学",
    "南开大学",
    "天津大学",
    "大连理工大学",
    "吉林大学",
    "哈尔滨工业大学",
    "复旦大学",
    "同济大学",
    "上海交通大学",
    "华东师范大学",
    "南京大学",
    "东南大学",
    "浙江大学",
    "中国科学技术大学",
    "厦门大学",
    "山东大学",
    "武汉大学",
    "华中科技大学",
    "中南大学",
    "中山大学",
    "华南理工大学",
    "四川大学",
    "重庆大学",
    "电子科技大学",
    "西安交通大学",
    "西北工业大学",
    "兰州大学",
    "东北大学",
    "西北农林科技大学",
    "国防科技大学",
    "中国海洋大学",
    "湖南大学",
}

UNIVERSITY_211_PARTIAL: set[str] = {
    "中国政法大学",
    "中央财经大学",
    "北京邮电大学",
    "南京航空航天大学",
    "西安电子科技大学",
    "上海财经大学",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _tags(config: dict[str, Any]) -> set[str]:
    raw = config.get("tags")
    if not isinstance(raw, list):
        return set()
    return {str(item).strip().lower() for item in raw if str(item).strip()}


def _institution_name(source_name: str, source_id: str) -> str | None:
    if not source_name:
        return None
    head = source_name.split("-", 1)[0].strip()
    head = head.replace("(官方)", "").replace("（官方）", "").strip()
    return head or source_id or None


def _institution_tier(name: str | None) -> str | None:
    if not name:
        return None
    if name in UNIVERSITY_985:
        return "985"
    if name in UNIVERSITY_211_PARTIAL:
        return "211"
    return "other"


def _source_platform(config: dict[str, Any]) -> str:
    tags = _tags(config)
    crawler_class = _text(config.get("crawler_class")).lower()
    url = _text(config.get("url")).lower()
    method = _text(config.get("crawl_method")).lower()

    if crawler_class in {"twitter_kol", "twitter_search"}:
        return "x"
    if "youtube" in tags or "youtube.com" in url:
        return "youtube"
    if {"xiaoyuzhou", "podcast"} & tags:
        return "xiaoyuzhou"
    if method == "rss":
        return "rss"
    if crawler_class.endswith("_api") or crawler_class in {
        "gov_json_api",
        "samr_api",
        "hunyuan_api",
    }:
        return "api"
    return "web"


def _source_type(config: dict[str, Any]) -> str:
    dimension = _text(config.get("dimension")).lower()
    group = _text(config.get("group")).lower()
    method = _text(config.get("crawl_method")).lower()
    crawler_class = _text(config.get("crawler_class")).lower()
    tags = _tags(config)

    if method == "university_leadership" or group == "university_leadership_official":
        return "university_leadership"
    if dimension == "scholars" or method == "faculty":
        return "scholar_profile"
    if dimension in {"national_policy", "beijing_policy"}:
        return "policy_news"
    if dimension == "universities":
        return "university_news"
    if crawler_class == "twitter_kol" or "kol" in tags:
        return "social_kol"
    if crawler_class == "twitter_search" or "social" in tags or dimension == "sentiment":
        return "social_topic"
    if dimension == "technology":
        return "technology_news"
    if dimension == "industry":
        return "industry_news"
    if dimension == "talent":
        return "talent_news"
    if dimension == "events":
        return "event_news"
    if dimension == "personnel":
        return "personnel_news"
    return "general_news"


def _load_all_sources() -> list[dict[str, Any]]:
    sources_dir = settings.SOURCES_DIR if settings.SOURCES_DIR else (BASE_DIR / "sources")
    all_sources: list[dict[str, Any]] = []
    for yaml_file in sorted(Path(sources_dir).glob("*.yaml")):
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        dimension = data.get("dimension", yaml_file.stem)
        dimension_name = data.get("dimension_name")
        desc = data.get("description")
        default_keywords = data.get("default_keyword_filter", [])
        default_blacklist = data.get("default_keyword_blacklist", [])

        for source in data.get("sources", []) or []:
            source = dict(source)
            source.setdefault("dimension", dimension)
            source.setdefault("dimension_name", dimension_name)
            source.setdefault("dimension_description", desc)
            source.setdefault("source_file", yaml_file.name)
            if "keyword_filter" not in source:
                source["keyword_filter"] = default_keywords
            if "keyword_blacklist" not in source:
                source["keyword_blacklist"] = default_blacklist
            all_sources.append(source)
    return all_sources


def _is_schedulable_source(config: dict[str, Any]) -> bool:
    dimension = _text(config.get("dimension")).lower()
    crawl_method = _text(config.get("crawl_method")).lower()
    if dimension == "scholars":
        return False
    if crawl_method == "faculty":
        return False
    return True


def _build_row(config: dict[str, Any], now_dt: datetime) -> dict[str, Any]:
    source_id = _text(config.get("id"))
    meta = build_source_catalog_meta(config)

    return {
        "source_id": source_id,
        "source_name": meta.get("source_name"),
        "source_url": meta.get("source_url"),
        "dimension": meta.get("dimension"),
        "dimension_name": meta.get("dimension_name"),
        "taxonomy_version": meta.get("taxonomy_version"),
        "taxonomy_domain": meta.get("taxonomy_domain"),
        "taxonomy_domain_name": meta.get("taxonomy_domain_name"),
        "taxonomy_track": meta.get("taxonomy_track"),
        "taxonomy_track_name": meta.get("taxonomy_track_name"),
        "taxonomy_scope": meta.get("taxonomy_scope"),
        "taxonomy_scope_name": meta.get("taxonomy_scope_name"),
        "group_name": meta.get("group_name"),
        "source_file": meta.get("source_file"),
        "crawl_method": meta.get("crawl_method"),
        "crawler_class": meta.get("crawler_class"),
        "schedule": meta.get("schedule"),
        "crawl_interval_minutes": meta.get("crawl_interval_minutes"),
        "source_type": meta.get("source_type"),
        "source_platform": meta.get("source_platform"),
        "tags": meta.get("tags") or [],
        "is_enabled_default": bool(meta.get("is_enabled_default", True)),
        "is_supported": True,
        "institution_name": meta.get("institution_name"),
        "institution_tier": meta.get("institution_tier"),
        "updated_at": now_dt,
    }


async def _run() -> None:
    if settings.POSTGRES_DSN:
        conn = await asyncpg.connect(settings.POSTGRES_DSN)
    else:
        conn = await asyncpg.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
        )

    try:
        all_sources = _load_all_sources()
        sources = [cfg for cfg in all_sources if _is_schedulable_source(cfg)]
        now_dt = datetime.now(timezone.utc)
        rows = [_build_row(cfg, now_dt) for cfg in sources if _text(cfg.get("id"))]
        source_ids = [row["source_id"] for row in rows]
        columns_res = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'source_states'
            """
        )
        available_columns = {str(item["column_name"]) for item in columns_res}
        if "source_id" not in available_columns:
            raise RuntimeError("source_states.source_id column is missing")

        desired_columns = [
            "source_id",
            "source_name",
            "source_url",
            "dimension",
            "dimension_name",
            "taxonomy_version",
            "taxonomy_domain",
            "taxonomy_domain_name",
            "taxonomy_track",
            "taxonomy_track_name",
            "taxonomy_scope",
            "taxonomy_scope_name",
            "group_name",
            "source_file",
            "crawl_method",
            "crawler_class",
            "schedule",
            "crawl_interval_minutes",
            "source_type",
            "source_platform",
            "tags",
            "is_enabled_default",
            "is_supported",
            "institution_name",
            "institution_tier",
            "updated_at",
        ]
        active_columns = [col for col in desired_columns if col in available_columns]

        if active_columns:
            placeholders = ", ".join(f"${idx}" for idx in range(1, len(active_columns) + 1))
            col_list = ", ".join(active_columns)
            update_assignments = ", ".join(
                f"{col} = EXCLUDED.{col}" for col in active_columns if col != "source_id"
            )

            upsert_sql = f"""
            INSERT INTO source_states ({col_list})
            VALUES ({placeholders})
            ON CONFLICT (source_id) DO UPDATE SET
                {update_assignments}
            """
            tuples = [tuple(row.get(col) for col in active_columns) for row in rows]
            await conn.executemany(upsert_sql, tuples)

        marked_unsupported = 0
        deleted_missing = 0
        if source_ids:
            marked = await conn.fetch(
                """
                SELECT source_id
                FROM source_states
                WHERE source_id <> ALL($1::text[])
                """,
                source_ids,
            )
            marked_unsupported = len(marked)
            deleted = await conn.fetch(
                """
                DELETE FROM source_states
                WHERE source_id <> ALL($1::text[])
                RETURNING source_id
                """,
                source_ids,
            )
            deleted_missing = len(deleted)

        print(
            json.dumps(
                {
                    "total_configs": len(sources),
                    "upserted": len(rows),
                    "marked_unsupported": marked_unsupported,
                    "deleted_missing": deleted_missing,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_run())
