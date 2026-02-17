"""Policy Intelligence API endpoints."""
from fastapi import APIRouter, Query

from app.schemas.intel.policy import PolicyFeedResponse, PolicyOpportunitiesResponse
from app.services.intel.policy import service as policy_service

router = APIRouter()


@router.get("/feed", response_model=PolicyFeedResponse)
async def get_policy_feed(
    category: str | None = Query(None, description="Filter: 国家政策/北京政策/领导讲话/政策机会"),
    importance: str | None = Query(None, description="Filter: 紧急/重要/关注/一般"),
    min_match_score: int | None = Query(None, ge=0, le=100, description="Minimum matchScore"),
    keyword: str | None = Query(None, description="Search in title/summary/source/tags"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get policy intelligence feed for the Policy Intel Module."""
    return policy_service.get_policy_feed(
        category=category,
        importance=importance,
        min_match_score=min_match_score,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )


@router.get("/opportunities", response_model=PolicyOpportunitiesResponse)
async def get_policy_opportunities(
    status: str | None = Query(None, description="Filter: urgent/active/tracking"),
    min_match_score: int | None = Query(None, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get policy opportunities for the Intelligence Page table."""
    return policy_service.get_policy_opportunities(
        status=status,
        min_match_score=min_match_score,
        limit=limit,
        offset=offset,
    )


@router.get("/stats")
async def get_policy_stats():
    """Get summary statistics about processed policy data."""
    return policy_service.get_policy_stats()
