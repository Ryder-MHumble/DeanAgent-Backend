from __future__ import annotations

from typing import Any

SCHEDULE_TO_MINUTES: dict[str, int] = {
    "2h": 120,
    "4h": 240,
    "daily": 24 * 60,
    "daily_bj_4": 24 * 60,
    "weekly": 7 * 24 * 60,
    "monthly": 30 * 24 * 60,
}

_UNIVERSITY_985: set[str] = {
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

# 当前领导信源里包含的部分 211 扩展院校。
_UNIVERSITY_211_PARTIAL: set[str] = {
    "中国政法大学",
    "中央财经大学",
    "北京邮电大学",
    "南京航空航天大学",
    "西安电子科技大学",
    "上海财经大学",
    "北京交通大学",
    "北京科技大学",
    "华北电力大学",
    "武汉理工大学",
    "西南交通大学",
    "南京理工大学",
    "华东理工大学",
    "对外经济贸易大学",
}

_INSTITUTION_SUFFIXES: tuple[str, ...] = (
    "新闻网",
    "新闻动态",
    "新闻中心",
    "新闻",
    "要闻",
    "资讯",
    "官网",
    "官方网站",
    "(自动)",
    "（自动）",
)

_INSTITUTION_ALIASES: dict[str, str] = {
    "上海交大": "上海交通大学",
    "中国科大": "中国科学技术大学",
    "哈工大": "哈尔滨工业大学",
    "北航": "北京航空航天大学",
    "北理": "北京理工大学",
    "北师大": "北京师范大学",
    "北邮": "北京邮电大学",
    "人大": "中国人民大学",
    "华科": "华中科技大学",
    "西电": "西安电子科技大学",
    "国防科大": "国防科技大学",
}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_tags(config: dict[str, Any]) -> set[str]:
    raw = config.get("tags")
    if not isinstance(raw, list):
        return set()
    return {str(item).strip().lower() for item in raw if str(item).strip()}


def extract_institution_name(source_name: str, source_id: str) -> str | None:
    if not source_name:
        return None
    head = source_name.split("-", 1)[0].strip()
    if not head:
        return None
    # 兼容 “(官方)/(OFFICIAL)” 之类尾缀
    cleaned = (
        head.replace("(官方)", "")
        .replace("（官方）", "")
        .replace("(OFFICIAL)", "")
        .strip()
    )
    normalized = cleaned
    while normalized:
        changed = False
        for suffix in _INSTITUTION_SUFFIXES:
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)].strip(" -_()（）")
                changed = True
        if not changed:
            break

    if normalized in _INSTITUTION_ALIASES:
        return _INSTITUTION_ALIASES[normalized]
    return normalized or source_id or None


def infer_institution_tier(institution_name: str | None) -> str | None:
    if not institution_name:
        return None
    if institution_name in _UNIVERSITY_985:
        return "985"
    if institution_name in _UNIVERSITY_211_PARTIAL:
        return "211"
    return "other"


def infer_source_platform(config: dict[str, Any]) -> str:
    tags = _normalize_tags(config)
    crawler_class = _normalize_text(config.get("crawler_class")).lower()
    url = _normalize_text(config.get("url")).lower()
    crawl_method = _normalize_text(config.get("crawl_method")).lower()

    if crawler_class in {"twitter_kol", "twitter_search"}:
        return "x"
    if "youtube" in tags or "youtube.com" in url:
        return "youtube"
    if {"xiaoyuzhou", "podcast"} & tags:
        return "xiaoyuzhou"
    if crawl_method == "rss":
        return "rss"
    if crawler_class.endswith("_api") or crawler_class in {
        "gov_json_api",
        "samr_api",
        "hunyuan_api",
    }:
        return "api"
    return "web"


def infer_source_type(config: dict[str, Any]) -> str:
    dimension = _normalize_text(config.get("dimension")).lower()
    group = _normalize_text(config.get("group")).lower()
    crawl_method = _normalize_text(config.get("crawl_method")).lower()
    crawler_class = _normalize_text(config.get("crawler_class")).lower()
    tags = _normalize_tags(config)

    if crawl_method == "university_leadership" or group == "university_leadership_official":
        return "university_leadership"
    if dimension == "scholars" or crawl_method == "faculty":
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


def schedule_to_minutes(schedule: str | None) -> int | None:
    if schedule is None:
        return None
    return SCHEDULE_TO_MINUTES.get(str(schedule).strip().lower())


def build_source_catalog_meta(config: dict[str, Any]) -> dict[str, Any]:
    source_name = _normalize_text(config.get("name"))
    source_id = _normalize_text(config.get("id"))
    source_platform = infer_source_platform(config)
    source_type = infer_source_type(config)
    if source_type.startswith("social_"):
        source_name = {
            "x": "Twitter",
            "youtube": "YouTube",
            "linkedin": "LinkedIn",
            "xiaoyuzhou": "小宇宙",
        }.get(source_platform, source_name or source_id)
    institution_name = extract_institution_name(source_name, source_id)
    schedule = _normalize_text(config.get("schedule")) or "daily"
    tags_raw = config.get("tags", [])
    tags = [str(tag).strip() for tag in tags_raw] if isinstance(tags_raw, list) else []

    return {
        "source_name": source_name or source_id,
        "source_url": _normalize_text(config.get("url")) or None,
        "dimension": _normalize_text(config.get("dimension")) or None,
        "dimension_name": _normalize_text(config.get("dimension_name")) or None,
        "group_name": _normalize_text(config.get("group")) or None,
        "source_file": _normalize_text(config.get("source_file")) or None,
        "crawl_method": _normalize_text(config.get("crawl_method")) or "static",
        "crawler_class": _normalize_text(config.get("crawler_class")) or None,
        "schedule": schedule,
        "crawl_interval_minutes": schedule_to_minutes(schedule),
        "source_type": source_type,
        "source_platform": source_platform,
        "is_enabled_default": bool(config.get("is_enabled", True)),
        "tags": tags,
        "institution_name": institution_name,
        "institution_tier": infer_institution_tier(institution_name),
    }
