"""Business logic for Tech Frontier module."""
from __future__ import annotations

import hashlib
import logging
from datetime import date

from app.schemas.business.tech import (
    HotTopic,
    HotTopicResponse,
    IndustryNewsItem,
    IndustryNewsResponse,
    TechTrend,
    TechTrendResponse,
)
from app.services.json_reader import get_articles
from app.services.llm_service import LLMError, call_llm_json

logger = logging.getLogger(__name__)


def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]


# Keywords for news type classification
TYPE_KEYWORDS = {
    "投融资": ["融资", "投资", "IPO", "上市", "估值", "轮", "种子轮", "天使轮", "A轮", "B轮", "C轮"],
    "新产品": ["发布", "推出", "新品", "上线", "launch", "release", "GPT", "模型", "开源"],
    "政策": ["政策", "监管", "法规", "规定", "管理办法", "regulation"],
    "收购": ["收购", "并购", "合并", "acquisition", "merge"],
}

IMPACT_KEYWORDS = {
    "重大": ["重大", "突破", "首次", "颠覆", "billion", "十亿", "百亿"],
    "较大": ["重要", "显著", "较大", "million", "亿"],
}


def _classify_type(title: str) -> str:
    title_lower = title.lower()
    for t, keywords in TYPE_KEYWORDS.items():
        if any(k.lower() in title_lower for k in keywords):
            return t
    return "其他"


def _assess_impact(title: str) -> str:
    for level, keywords in IMPACT_KEYWORDS.items():
        if any(k in title for k in keywords):
            return level
    return "一般"


def get_industry_news(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
) -> IndustryNewsResponse:
    """Get industry news from industry + technology dimensions."""
    industry_articles = get_articles("industry", date_from=date_from, date_to=date_to)
    tech_articles = get_articles(
        "technology", group="domestic_media", date_from=date_from, date_to=date_to,
    )

    all_articles = industry_articles + tech_articles
    # Deduplicate by url
    seen_urls: set[str] = set()
    unique: list[dict] = []
    for art in all_articles:
        url = art.get("url", "")
        if url not in seen_urls:
            seen_urls.add(url)
            unique.append(art)

    # Sort by date
    unique.sort(key=lambda x: x.get("published_at", "") or "", reverse=True)

    items: list[IndustryNewsItem] = []
    for art in unique[:limit]:
        title = art.get("title", "")
        items.append(IndustryNewsItem(
            id=_make_id(art.get("url", "")),
            title=title,
            url=art.get("url", ""),
            source=art.get("source_name", art.get("source_id", "")),
            news_type=_classify_type(title),
            date=art.get("published_at"),
            impact=_assess_impact(title),
        ))

    return IndustryNewsResponse(items=items, total=len(items))


def get_hot_topics(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 20,
) -> HotTopicResponse:
    """Get hot topics from tech community sources (Phase 1: rule-based)."""
    articles = get_articles(
        "technology", group="community", date_from=date_from, date_to=date_to,
    )

    items: list[HotTopic] = []
    for art in articles[:limit]:
        items.append(HotTopic(
            id=_make_id(art.get("url", "")),
            title=art.get("title", ""),
            tags=art.get("tags", []),
        ))

    return HotTopicResponse(items=items, total=len(items))


async def get_tech_trends_enhanced(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 10,
) -> TechTrendResponse:
    """Get tech trends with LLM analysis (Phase 2)."""
    articles = get_articles("technology", date_from=date_from, date_to=date_to)

    if not articles:
        return TechTrendResponse(items=[], total=0)

    titles = [f"- {a.get('title', '')} ({a.get('source_name', '')})" for a in articles[:30]]
    titles_text = "\n".join(titles)

    system_prompt = (
        "你是AI技术趋势分析师。从以下新闻标题中提取5-10个技术趋势。返回JSON：\n"
        '{"trends": [{"topic": "主题", "heat_trend": "surging|rising|stable|declining", '
        '"heat_label": "+150%", "key_metric": "关键指标", "ai_insight": "趋势分析"}]}'
    )
    prompt = f"从以下AI/科技新闻中提取技术趋势：\n{titles_text}"

    try:
        result = await call_llm_json(prompt=prompt, system_prompt=system_prompt)
        trends_data = result.get("trends", []) if isinstance(result, dict) else result

        items: list[TechTrend] = []
        for i, t in enumerate(trends_data[:limit]):
            items.append(TechTrend(
                id=f"trend_{i}",
                topic=t.get("topic", ""),
                heat_trend=t.get("heat_trend", "stable"),
                heat_label=t.get("heat_label", ""),
                key_metric=t.get("key_metric", ""),
                ai_insight=t.get("ai_insight", ""),
            ))

        return TechTrendResponse(items=items, total=len(items))

    except LLMError as e:
        logger.warning("LLM tech trends analysis failed: %s", e)
        return TechTrendResponse(items=[], total=0)


async def get_hot_topics_enhanced(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 15,
) -> HotTopicResponse:
    """Get hot topics with LLM enhancement (Phase 2)."""
    articles = get_articles(
        "technology", group="community", date_from=date_from, date_to=date_to,
    )

    if not articles:
        return HotTopicResponse(items=[], total=0)

    titles = [f"- {a.get('title', '')}" for a in articles[:40]]
    titles_text = "\n".join(titles)

    system_prompt = (
        "你是AI社区热点分析师。从以下讨论标题中提取热点话题。返回JSON：\n"
        '{"topics": [{"title": "话题", "heat": 85, "trend": "up|stable|new", '
        '"tags": ["标签"], "summary": "话题概要", "ai_analysis": "分析"}]}'
    )
    prompt = f"从以下AI社区讨论中提取热点话题（合并相似主题）：\n{titles_text}"

    try:
        result = await call_llm_json(prompt=prompt, system_prompt=system_prompt)
        topics_data = result.get("topics", []) if isinstance(result, dict) else result

        items: list[HotTopic] = []
        for i, t in enumerate(topics_data[:limit]):
            items.append(HotTopic(
                id=f"hot_{i}",
                title=t.get("title", ""),
                heat=t.get("heat", 50),
                max_heat=100,
                trend=t.get("trend", "stable"),
                tags=t.get("tags", []),
                summary=t.get("summary", ""),
                ai_analysis=t.get("ai_analysis", ""),
            ))

        return HotTopicResponse(items=items, total=len(items))

    except LLMError as e:
        logger.warning("LLM hot topics analysis failed: %s", e)
        return get_hot_topics(date_from, date_to, limit)
