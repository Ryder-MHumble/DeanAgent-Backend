"""Business logic for Policy Intelligence module."""
from __future__ import annotations

import hashlib
import logging
from datetime import date

from app.schemas.business.policy import PolicyItem, PolicyListResponse
from app.services.json_reader import get_articles
from app.services.llm_service import LLMError, call_llm_json

logger = logging.getLogger(__name__)

# Source ID → agency name mapping
AGENCY_MAP = {
    "gov_cn_zhengce": "国务院",
    "ndrc_policy": "国家发展改革委",
    "moe_policy": "教育部",
    "most_policy": "科学技术部",
    "miit_policy": "工业和信息化部",
    "beijing_zhengce": "北京市政府",
    "bjkw_policy": "北京市科委/中关村管委会",
    "bjjw_policy": "北京市教委",
    "bjrsj_policy": "北京市人社局",
    "ncsti_policy": "国际科创中心",
    "bjfgw_policy": "北京市发改委",
    "beijing_ywdt": "首都之窗",
    "bjrd_renshi": "北京市人大常委会",
}


def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def _detect_status(title: str) -> str:
    urgent_keywords = ["紧急", "立即", "截止", "最后"]
    if any(k in title for k in urgent_keywords):
        return "urgent"
    active_keywords = ["通知", "公告", "意见", "办法", "规定", "方案"]
    if any(k in title for k in active_keywords):
        return "active"
    return "tracking"


def get_policy_list(
    dimension: str,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
) -> PolicyListResponse:
    """
    Get policy articles for a dimension (national_policy or beijing_policy).

    Phase 1: Rule-based processing (no LLM).
    """
    articles = get_articles(dimension, date_from=date_from, date_to=date_to)

    agency_type = "national" if dimension == "national_policy" else "beijing"

    items: list[PolicyItem] = []
    for art in articles[:limit]:
        source_id = art.get("source_id", "")
        items.append(PolicyItem(
            id=_make_id(art.get("url", "")),
            title=art.get("title", ""),
            url=art.get("url", ""),
            agency=AGENCY_MAP.get(source_id, source_id),
            agency_type=agency_type,
            status=_detect_status(art.get("title", "")),
            published_at=art.get("published_at"),
            source_id=source_id,
            source_name=art.get("source_name", ""),
        ))

    return PolicyListResponse(
        items=items,
        total=len(items),
        dimension=dimension,
    )


async def get_policy_list_enhanced(
    dimension: str,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 30,
) -> PolicyListResponse:
    """
    Get policy articles with LLM enhancement (Phase 2).

    Adds: match_score, ai_insight, funding extraction.
    """
    base = get_policy_list(dimension, date_from, date_to, limit)

    if not base.items:
        return base

    # Batch articles for LLM processing
    titles = [f"- {item.title} ({item.agency})" for item in base.items[:20]]
    titles_text = "\n".join(titles)

    system_prompt = (
        "你是一个政策分析助手。针对中关村人工智能研究院的发展需求，"
        "分析以下政策的相关性。返回 JSON 数组，每项包含：\n"
        '{"index": 0, "match_score": 75, "status": "active", "ai_insight": "简要分析"}'
    )
    prompt = f"分析以下{dimension}政策与AI研究院的相关性：\n{titles_text}"

    try:
        result = await call_llm_json(prompt=prompt, system_prompt=system_prompt)
        if isinstance(result, dict):
            result = result.get("items", result.get("policies", []))

        for entry in result:
            idx = entry.get("index", -1)
            if 0 <= idx < len(base.items):
                item = base.items[idx]
                item.match_score = entry.get("match_score", 0)
                item.ai_insight = entry.get("ai_insight", "")
                status = entry.get("status")
                if status in ("urgent", "active", "tracking"):
                    item.status = status

    except LLMError as e:
        logger.warning("LLM enhancement failed, returning base data: %s", e)

    return base
