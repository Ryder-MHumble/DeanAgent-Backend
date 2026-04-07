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

_TAXONOMY_DOMAIN_NAMES: dict[str, str] = {
    "policy_governance": "政策治理",
    "education_research": "高校与科研生态",
    "technology_frontier": "技术前沿与创新",
    "industry_market": "产业与资本市场",
    "talent_personnel": "人才与组织发展",
    "academic_events": "学术会议与活动",
    "social_intelligence": "社交情报与舆情",
    "general_monitoring": "综合监测",
}

_TAXONOMY_TRACK_NAMES: dict[str, str] = {
    "policy_national": "国家政策",
    "policy_local_beijing": "北京市政策",
    "personnel_appointments": "人事任免",
    "university_leadership": "高校领导班子",
    "university_news": "高校新闻",
    "ai_research_institutes": "AI 研究机构",
    "research_awards": "科研奖励与评选",
    "education_governance": "教育行政动态",
    "education_aggregators": "高教资讯聚合",
    "scholar_profiles": "学者与师资库",
    "technology_media": "技术媒体",
    "company_releases": "企业官方发布",
    "research_feeds": "论文与研究动态",
    "tech_communities": "技术社区与开源",
    "social_kol_monitoring": "社媒 KOL 监测",
    "industry_media": "产业媒体",
    "investment_financing": "投融资动态",
    "talent_programs": "人才项目与学术影响力",
    "conferences_events": "会议与活动",
    "generic_monitoring": "通用监测",
}

_TAXONOMY_SCOPE_NAMES: dict[str, str] = {
    "national": "国家级",
    "beijing": "北京市",
    "university": "高校",
    "research_institute": "科研机构",
    "provincial": "省市教育部门",
    "china": "中国",
    "global": "全球",
    "mixed": "综合",
    "social_platform": "社交平台",
}

_PROFESSIONAL_DIMENSION_NAMES: dict[str, str] = {
    "national_policy": "国家政策治理",
    "beijing_policy": "北京市政策治理",
    "technology": "技术前沿与创新",
    "talent": "人才与学术发展",
    "industry": "产业与投融资",
    "sentiment": "社交情报与舆情",
    "twitter": "社交媒体监测",
    "universities": "高校与科研生态",
    "events": "学术会议与活动",
    "personnel": "组织人事动态",
    "scholars": "学者与师资库",
}

_LEGACY_DIMENSION_NAME_ALIASES: dict[str, str] = {
    "对国家": "国家政策治理",
    "对北京": "北京市政策治理",
    "对技术": "技术前沿与创新",
    "对人才": "人才与学术发展",
    "对产业": "产业与投融资",
    "对学院舆情": "社交情报与舆情",
    "对高校": "高校与科研生态",
    "对日程": "学术会议与活动",
    "对人事": "组织人事动态",
    "高校师资": "学者与师资库",
}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_tags(config: dict[str, Any]) -> set[str]:
    raw = config.get("tags")
    if not isinstance(raw, list):
        return set()
    return {str(item).strip().lower() for item in raw if str(item).strip()}


def normalize_dimension_name(dimension: Any, dimension_name: Any) -> str | None:
    raw_name = _normalize_text(dimension_name)
    if raw_name in _LEGACY_DIMENSION_NAME_ALIASES:
        return _LEGACY_DIMENSION_NAME_ALIASES[raw_name]
    dim_key = _normalize_text(dimension).lower()
    if dim_key in _PROFESSIONAL_DIMENSION_NAMES:
        return _PROFESSIONAL_DIMENSION_NAMES[dim_key]
    return raw_name or None


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


def _infer_taxonomy_track(config: dict[str, Any]) -> str:
    dimension = _normalize_text(config.get("dimension")).lower()
    group = _normalize_text(config.get("group")).lower()
    source_type = _normalize_text(config.get("source_type")).lower()
    if not source_type:
        source_type = infer_source_type(config)
    tags = _normalize_tags(config)

    if source_type in {"social_kol", "social_topic"} or group == "social_platform":
        return "social_kol_monitoring"
    if source_type == "university_leadership":
        return "university_leadership"
    if source_type == "personnel_news":
        return "personnel_appointments"
    if dimension == "national_policy":
        return "policy_national"
    if dimension == "beijing_policy":
        return "policy_local_beijing"
    if source_type == "scholar_profile":
        return "scholar_profiles"
    if source_type == "university_news":
        if group == "ai_institutes":
            return "ai_research_institutes"
        if group == "awards":
            return "research_awards"
        if group == "provincial":
            return "education_governance"
        if group == "aggregators":
            return "education_aggregators"
        return "university_news"
    if source_type == "technology_news":
        if group == "company_blogs" or "company_blog" in tags:
            return "company_releases"
        if group == "academic" or {"academic", "arxiv", "papers"} & tags:
            return "research_feeds"
        if group == "community" or {"community", "github", "reddit"} & tags:
            return "tech_communities"
        return "technology_media"
    if source_type == "industry_news":
        if group == "investment" or {"investment", "financing", "vc"} & tags:
            return "investment_financing"
        return "industry_media"
    if source_type == "talent_news":
        return "talent_programs"
    if source_type == "event_news":
        return "conferences_events"
    return "generic_monitoring"


def _infer_taxonomy_domain(track: str) -> str:
    if track in {"policy_national", "policy_local_beijing"}:
        return "policy_governance"
    if track in {
        "university_news",
        "ai_research_institutes",
        "research_awards",
        "education_governance",
        "education_aggregators",
        "scholar_profiles",
    }:
        return "education_research"
    if track in {"technology_media", "company_releases", "research_feeds", "tech_communities"}:
        return "technology_frontier"
    if track in {"industry_media", "investment_financing"}:
        return "industry_market"
    if track in {"personnel_appointments", "university_leadership", "talent_programs"}:
        return "talent_personnel"
    if track == "conferences_events":
        return "academic_events"
    if track == "social_kol_monitoring":
        return "social_intelligence"
    return "general_monitoring"


def _infer_taxonomy_scope(config: dict[str, Any], track: str) -> str:
    dimension = _normalize_text(config.get("dimension")).lower()
    group = _normalize_text(config.get("group")).lower()
    source_type = _normalize_text(config.get("source_type")).lower()
    if not source_type:
        source_type = infer_source_type(config)
    source_platform = _normalize_text(config.get("source_platform")).lower()
    if not source_platform:
        source_platform = infer_source_platform(config)
    tags = _normalize_tags(config)

    if dimension == "national_policy":
        return "national"
    if dimension == "beijing_policy":
        return "beijing"
    if track == "social_kol_monitoring" or source_type in {"social_kol", "social_topic"}:
        return "social_platform"
    if source_type == "university_leadership":
        return "university"
    if source_type == "personnel_news":
        return "national"
    if source_type == "scholar_profile":
        return "university"
    if source_type == "university_news":
        if group == "ai_institutes":
            return "research_institute"
        if group == "provincial":
            return "provincial"
        if group in {"awards", "aggregators"}:
            return "china"
        return "university"
    if source_type in {"industry_news", "talent_news"}:
        if {"nature_index", "overseas", "international"} & tags:
            return "global"
        return "china"
    if source_type == "event_news":
        if {"international", "global", "wikicfp", "aideadlines"} & tags:
            return "global"
        return "china"
    if source_type == "technology_news":
        if source_platform in {"x", "youtube", "linkedin"}:
            return "global"
        if {"international", "global"} & tags:
            return "global"
        if {"domestic", "cn_ai", "china"} & tags:
            return "china"
        return "mixed"
    return "mixed"


def build_source_taxonomy(config: dict[str, Any]) -> dict[str, str]:
    """Build professional taxonomy fields while keeping legacy dimensions unchanged."""
    adapted = dict(config)
    if "group" not in adapted and "group_name" in adapted:
        adapted["group"] = adapted.get("group_name")

    track = _infer_taxonomy_track(adapted)
    domain = _infer_taxonomy_domain(track)
    scope = _infer_taxonomy_scope(adapted, track)

    return {
        "taxonomy_version": "v2",
        "taxonomy_domain": domain,
        "taxonomy_domain_name": _TAXONOMY_DOMAIN_NAMES.get(domain, domain),
        "taxonomy_track": track,
        "taxonomy_track_name": _TAXONOMY_TRACK_NAMES.get(track, track),
        "taxonomy_scope": scope,
        "taxonomy_scope_name": _TAXONOMY_SCOPE_NAMES.get(scope, scope),
    }


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

    taxonomy = build_source_taxonomy(
        {
            **config,
            "source_type": source_type,
            "source_platform": source_platform,
        }
    )

    return {
        "source_name": source_name or source_id,
        "source_url": _normalize_text(config.get("url")) or None,
        "dimension": _normalize_text(config.get("dimension")) or None,
        "dimension_name": normalize_dimension_name(
            config.get("dimension"), config.get("dimension_name")
        ),
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
        **taxonomy,
    }
