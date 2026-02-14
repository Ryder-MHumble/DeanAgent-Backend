"""Business logic for University Ecosystem module."""
from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from datetime import date

from app.schemas.business.university import (
    PeerInstitution,
    PeerListResponse,
    PersonnelChange,
    PersonnelListResponse,
    ResearchListResponse,
    ResearchOutput,
)
from app.services.json_reader import get_articles

logger = logging.getLogger(__name__)

# Map source_id to institution name
INSTITUTION_MAP = {
    "tsinghua_news": "清华大学",
    "pku_news": "北京大学",
    "ustc_news": "中国科学技术大学",
    "sjtu_news": "上海交通大学",
    "fudan_news": "复旦大学",
    "baai_news": "北京智源人工智能研究院",
    "tsinghua_air": "清华大学智能产业研究院",
    "shlab_news": "上海人工智能实验室",
    "pcl_news": "鹏城实验室",
    "ia_cas_news": "中国科学院自动化研究所",
    "ict_cas_news": "中国科学院计算技术研究所",
}

PERSONNEL_KEYWORDS = [
    "任命", "任职", "调任", "免去", "离职", "就任", "上任", "聘任", "续任",
    "院长", "副院长", "书记", "校长", "副校长", "主任", "所长", "理事长",
    "人事", "干部", "选举", "当选",
]

AWARD_KEYWORDS = [
    "院士", "Fellow", "获奖", "荣获", "授予", "表彰", "国家科技奖",
    "杰青", "优青", "长江学者", "万人计划",
]


def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def _is_personnel_related(title: str) -> bool:
    return any(k in title for k in PERSONNEL_KEYWORDS)


def _is_award_related(title: str) -> bool:
    return any(k in title for k in AWARD_KEYWORDS)


def get_peer_dynamics(
    date_from: date | None = None,
    date_to: date | None = None,
) -> PeerListResponse:
    """
    Get peer institution dynamics grouped by institution.

    Aggregates articles from university_news and ai_institutes groups.
    """
    news_articles = get_articles(
        "universities", group="university_news", date_from=date_from, date_to=date_to,
    )
    institute_articles = get_articles(
        "universities", group="ai_institutes", date_from=date_from, date_to=date_to,
    )

    all_articles = news_articles + institute_articles

    # Group by source_id (institution)
    by_source: dict[str, list[dict]] = defaultdict(list)
    for art in all_articles:
        sid = art.get("source_id", "unknown")
        by_source[sid].append(art)

    items: list[PeerInstitution] = []
    for source_id, arts in by_source.items():
        # Sort by date, pick latest
        arts.sort(key=lambda x: x.get("published_at", "") or "", reverse=True)
        latest = arts[0] if arts else {}

        name = INSTITUTION_MAP.get(source_id, latest.get("source_name", source_id))
        count = len(arts)

        # Determine threat level based on activity
        threat = "normal"
        if count >= 15:
            threat = "critical"
        elif count >= 8:
            threat = "warning"

        items.append(PeerInstitution(
            id=source_id,
            name=name,
            activity_level=count,
            latest_action=latest.get("title", ""),
            action_type="news",
            threat_level=threat,
            recent_count=count,
        ))

    # Sort by activity level desc
    items.sort(key=lambda x: x.activity_level, reverse=True)

    return PeerListResponse(items=items, total=len(items))


def get_personnel_changes(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
) -> PersonnelListResponse:
    """
    Get personnel changes from universities dimension.

    Phase 1: Keyword filtering on titles.
    """
    # Personnel group
    personnel_articles = get_articles(
        "universities", group="personnel", date_from=date_from, date_to=date_to,
    )
    # Also check university news for personnel-related titles
    news_articles = get_articles(
        "universities", group="university_news", date_from=date_from, date_to=date_to,
    )

    all_articles = personnel_articles + [
        a for a in news_articles if _is_personnel_related(a.get("title", ""))
    ]

    items: list[PersonnelChange] = []
    for art in all_articles[:limit]:
        source_id = art.get("source_id", "")
        items.append(PersonnelChange(
            id=_make_id(art.get("url", "")),
            title=art.get("title", ""),
            url=art.get("url", ""),
            institution=INSTITUTION_MAP.get(source_id, art.get("source_name", "")),
            date=art.get("published_at"),
            source_id=source_id,
            # Person/position extraction requires LLM (Phase 2)
        ))

    return PersonnelListResponse(items=items, total=len(items))


def get_research_outputs(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
) -> ResearchListResponse:
    """Get research outputs from awards group."""
    articles = get_articles(
        "universities", group="awards", date_from=date_from, date_to=date_to,
    )

    items: list[ResearchOutput] = []
    for art in articles[:limit]:
        title = art.get("title", "")
        source_id = art.get("source_id", "")

        # Basic type detection
        output_type = "获奖"
        if "论文" in title or "paper" in title.lower():
            output_type = "论文"
        elif "专利" in title or "patent" in title.lower():
            output_type = "专利"

        items.append(ResearchOutput(
            id=_make_id(art.get("url", "")),
            title=title,
            institution=art.get("source_name", ""),
            output_type=output_type,
            date=art.get("published_at"),
        ))

    return ResearchListResponse(items=items, total=len(items))
