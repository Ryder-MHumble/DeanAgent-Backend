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
    source_name = _text(config.get("name")) or source_id
    source_schedule = _text(config.get("schedule")) or "daily"
    source_platform = _source_platform(config)
    source_type = _source_type(config)
    if source_type.startswith("social_"):
        source_name = {
            "x": "Twitter",
            "youtube": "YouTube",
            "linkedin": "LinkedIn",
            "xiaoyuzhou": "小宇宙",
        }.get(source_platform, source_name or source_id)
    institution_name = _institution_name(source_name, source_id)
    raw_tags = config.get("tags")
    tags = [str(item).strip() for item in raw_tags] if isinstance(raw_tags, list) else []

    return {
        "source_id": source_id,
        "source_name": source_name,
        "source_url": _text(config.get("url")) or None,
        "dimension": _text(config.get("dimension")) or None,
        "dimension_name": _text(config.get("dimension_name")) or None,
        "group_name": _text(config.get("group")) or None,
        "source_file": _text(config.get("source_file")) or None,
        "crawl_method": _text(config.get("crawl_method")) or "static",
        "crawler_class": _text(config.get("crawler_class")) or None,
        "schedule": source_schedule,
        "crawl_interval_minutes": SCHEDULE_TO_MINUTES.get(source_schedule.lower()),
        "source_type": source_type,
        "source_platform": source_platform,
        "tags": tags,
        "is_enabled_default": bool(config.get("is_enabled", True)),
        "is_supported": True,
        "institution_name": institution_name,
        "institution_tier": _institution_tier(institution_name),
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

        upsert_sql = """
        INSERT INTO source_states (
            source_id, source_name, source_url, dimension, dimension_name, group_name,
            source_file, crawl_method, crawler_class, schedule, crawl_interval_minutes,
            source_type, source_platform, tags, is_enabled_default, is_supported,
            institution_name, institution_tier, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6,
            $7, $8, $9, $10, $11,
            $12, $13, $14, $15, $16,
            $17, $18, $19
        )
        ON CONFLICT (source_id) DO UPDATE SET
            source_name = EXCLUDED.source_name,
            source_url = EXCLUDED.source_url,
            dimension = EXCLUDED.dimension,
            dimension_name = EXCLUDED.dimension_name,
            group_name = EXCLUDED.group_name,
            source_file = EXCLUDED.source_file,
            crawl_method = EXCLUDED.crawl_method,
            crawler_class = EXCLUDED.crawler_class,
            schedule = EXCLUDED.schedule,
            crawl_interval_minutes = EXCLUDED.crawl_interval_minutes,
            source_type = EXCLUDED.source_type,
            source_platform = EXCLUDED.source_platform,
            tags = EXCLUDED.tags,
            is_enabled_default = EXCLUDED.is_enabled_default,
            is_supported = EXCLUDED.is_supported,
            institution_name = EXCLUDED.institution_name,
            institution_tier = EXCLUDED.institution_tier,
            updated_at = EXCLUDED.updated_at
        """

        tuples = [
            (
                row["source_id"],
                row["source_name"],
                row["source_url"],
                row["dimension"],
                row["dimension_name"],
                row["group_name"],
                row["source_file"],
                row["crawl_method"],
                row["crawler_class"],
                row["schedule"],
                row["crawl_interval_minutes"],
                row["source_type"],
                row["source_platform"],
                row["tags"],
                row["is_enabled_default"],
                row["is_supported"],
                row["institution_name"],
                row["institution_tier"],
                row["updated_at"],
            )
            for row in rows
        ]
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
