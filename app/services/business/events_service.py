"""Business logic for Events module."""
from __future__ import annotations

import hashlib
import logging
from datetime import date

from app.schemas.business.events import EventListResponse, RecommendedActivity
from app.services.json_reader import get_articles

logger = logging.getLogger(__name__)


def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]


# Category detection keywords
CATEGORY_KEYWORDS = {
    "NLP": ["NLP", "natural language", "语言模型", "LLM", "大模型"],
    "CV": ["computer vision", "图像", "视觉", "CVPR", "ICCV", "ECCV"],
    "ML": ["machine learning", "ICML", "NeurIPS", "ICLR", "机器学习"],
    "AI": ["artificial intelligence", "AI", "AAAI", "IJCAI", "人工智能"],
    "Robotics": ["robot", "机器人", "自动驾驶", "autonomous"],
    "Data": ["数据", "data", "KDD", "SIGMOD", "database"],
}


def _detect_category(title: str) -> str:
    title_lower = title.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(k.lower() in title_lower for k in keywords):
            return cat
    return "AI"


def get_events_list(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
) -> EventListResponse:
    """Get events/conferences from events dimension."""
    articles = get_articles("events", date_from=date_from, date_to=date_to)

    items: list[RecommendedActivity] = []
    for art in articles[:limit]:
        title = art.get("title", "")
        items.append(RecommendedActivity(
            id=_make_id(art.get("url", "")),
            name=title,
            url=art.get("url", ""),
            date=art.get("published_at"),
            category=_detect_category(title),
            source_id=art.get("source_id", ""),
            source_name=art.get("source_name", ""),
        ))

    return EventListResponse(items=items, total=len(items))
