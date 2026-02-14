"""Tech Frontier API endpoints."""
from datetime import date

from fastapi import APIRouter, Query

from app.schemas.business.tech import (
    HotTopicResponse,
    IndustryNewsResponse,
    TechTrendResponse,
)
from app.services.business.tech_service import (
    get_hot_topics,
    get_hot_topics_enhanced,
    get_industry_news,
    get_tech_trends_enhanced,
)

router = APIRouter()


@router.get("/industry-news", response_model=IndustryNewsResponse)
async def list_industry_news(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List industry news articles with type classification."""
    return get_industry_news(date_from=date_from, date_to=date_to, limit=limit)


@router.get("/trends", response_model=TechTrendResponse)
async def list_tech_trends(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(10, ge=1, le=30),
):
    """Get AI/tech trend analysis (requires LLM)."""
    return await get_tech_trends_enhanced(date_from=date_from, date_to=date_to, limit=limit)


@router.get("/hot-topics", response_model=HotTopicResponse)
async def list_hot_topics(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    enhanced: bool = Query(False, description="Enable LLM enhancement"),
):
    """Get hot topics from tech communities."""
    if enhanced:
        return await get_hot_topics_enhanced(date_from=date_from, date_to=date_to, limit=limit)
    return get_hot_topics(date_from=date_from, date_to=date_to, limit=limit)
