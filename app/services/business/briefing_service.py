"""Business logic for Home Briefing module (daily summary, metrics, priorities)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.schemas.business.briefing import (
    DailySummary,
    DailySummaryResponse,
    MetricCard,
    MetricsResponse,
    PriorityItem,
    PriorityResponse,
)
from app.services.json_reader import get_articles, get_dimension_stats
from app.services.llm_service import LLMError, call_llm_json

logger = logging.getLogger(__name__)

DIMENSION_LABELS = {
    "national_policy": "国家政策",
    "beijing_policy": "北京政策",
    "technology": "科技前沿",
    "industry": "产业动态",
    "universities": "高校生态",
    "talent": "人才雷达",
    "events": "活动日程",
    "sentiment": "学院舆情",
}


def get_metrics() -> MetricsResponse:
    """Get dashboard metric cards for all dimensions."""
    stats = get_dimension_stats()

    cards: list[MetricCard] = []
    for dim, label in DIMENSION_LABELS.items():
        dim_stats = stats.get(dim, {})
        cards.append(MetricCard(
            dimension=dim,
            dimension_label=label,
            total_items=dim_stats.get("total_items", 0),
            source_count=dim_stats.get("source_count", 0),
            latest_crawl=dim_stats.get("latest_crawl"),
        ))

    return MetricsResponse(
        cards=cards,
        total_dimensions=len(cards),
    )


def get_priorities(limit: int = 10) -> PriorityResponse:
    """
    Get priority items across all dimensions (Phase 1: rule-based scoring).

    Scoring heuristic:
    - Personnel changes: +30 (need to congratulate)
    - Policy with urgent keywords: +25
    - Award/honor: +20
    - Recent (today): +15
    - National > Beijing > other dimensions: +10/+5/+0
    """
    priority_items: list[tuple[float, dict, str]] = []

    # Check personnel changes (high priority: congratulations)
    personnel_keywords = ["任命", "院长", "校长", "书记", "当选", "院士", "Fellow"]
    personnel = get_articles("universities", group="personnel")
    for art in personnel[:20]:
        title = art.get("title", "")
        score = 50.0
        if any(k in title for k in personnel_keywords):
            score += 30
        priority_items.append((score, art, "universities"))

    # Check national policy (urgent items)
    national = get_articles("national_policy")
    for art in national[:10]:
        title = art.get("title", "")
        score = 40.0
        if any(k in title for k in ["紧急", "重大", "截止"]):
            score += 25
        priority_items.append((score, art, "national_policy"))

    # Check awards
    awards = get_articles("universities", group="awards")
    for art in awards[:10]:
        score = 45.0
        priority_items.append((score, art, "universities"))

    # Sort by score desc
    priority_items.sort(key=lambda x: x[0], reverse=True)

    items: list[PriorityItem] = []
    seen_urls: set[str] = set()
    for score, art, dim in priority_items[:limit]:
        url = art.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        items.append(PriorityItem(
            id=art.get("url_hash", "")[:12] or str(len(items)),
            title=art.get("title", ""),
            url=url,
            dimension=dim,
            source_id=art.get("source_id", ""),
            score=score,
        ))

    return PriorityResponse(items=items, total=len(items))


async def get_daily_summary() -> DailySummaryResponse:
    """Generate AI daily summary across all dimensions (Phase 2: LLM)."""
    # Collect top articles from each dimension
    dimension_summaries: list[str] = []
    total_articles = 0

    for dim in DIMENSION_LABELS:
        articles = get_articles(dim)
        total_articles += len(articles)
        if articles:
            top_titles = [a.get("title", "") for a in articles[:5]]
            dim_label = DIMENSION_LABELS[dim]
            dimension_summaries.append(
                f"【{dim_label}】\n" + "\n".join(f"- {t}" for t in top_titles)
            )

    if not dimension_summaries:
        return DailySummaryResponse(summary=DailySummary(
            summary="暂无数据",
            generated_at=datetime.now(timezone.utc).isoformat(),
        ))

    all_text = "\n\n".join(dimension_summaries)

    system_prompt = (
        "你是中关村人工智能研究院的院长助理。请根据以下各维度的最新资讯，"
        "为院长撰写一份简洁的每日情报简报（300字以内）。"
        "重点关注：需要立即行动的事项、重要政策变化、值得祝贺的人、重大技术进展。"
        '返回 JSON: {"summary": "简报内容", "key_points": ["要点1", "要点2"]}'
    )
    prompt = f"以下是今日各维度最新资讯：\n\n{all_text}"

    try:
        result = await call_llm_json(prompt=prompt, system_prompt=system_prompt)
        summary_text = result.get("summary", "") if isinstance(result, dict) else str(result)

        return DailySummaryResponse(summary=DailySummary(
            summary=summary_text,
            generated_at=datetime.now(timezone.utc).isoformat(),
            dimensions_covered=list(DIMENSION_LABELS.keys()),
            total_articles_analyzed=total_articles,
        ))

    except LLMError as e:
        logger.warning("LLM daily summary generation failed: %s", e)
        return DailySummaryResponse(summary=DailySummary(
            summary=f"LLM 生成失败，共采集 {total_articles} 篇文章。",
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_articles_analyzed=total_articles,
        ))
