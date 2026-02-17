"""Personnel Intelligence API endpoints."""
from fastapi import APIRouter, Query

from app.schemas.intel.personnel import (
    PersonnelChangesResponse,
    PersonnelEnrichedFeedResponse,
    PersonnelEnrichedStatsResponse,
    PersonnelFeedResponse,
)
from app.services.intel.personnel import service as personnel_service

router = APIRouter()


@router.get("/feed", response_model=PersonnelFeedResponse)
async def get_personnel_feed(
    importance: str | None = Query(None, description="Filter: 紧急/重要/关注/一般"),
    min_match_score: int | None = Query(None, ge=0, le=100),
    keyword: str | None = Query(None, description="Search in title/name/position"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get personnel intelligence feed — articles with extracted changes."""
    return personnel_service.get_personnel_feed(
        importance=importance,
        min_match_score=min_match_score,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )


@router.get("/changes", response_model=PersonnelChangesResponse)
async def get_personnel_changes(
    department: str | None = Query(None, description="Filter by department"),
    action: str | None = Query(None, description="Filter: 任命/免去"),
    keyword: str | None = Query(None, description="Search in name/position/department"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get structured personnel changes — one entry per person per action."""
    return personnel_service.get_personnel_changes(
        department=department,
        action=action,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )


@router.get("/stats")
async def get_personnel_stats():
    """Get summary statistics about personnel data."""
    return personnel_service.get_personnel_stats()


@router.get("/enriched-feed", response_model=PersonnelEnrichedFeedResponse)
async def get_enriched_feed(
    group: str | None = Query(None, description="Filter: action/watch"),
    importance: str | None = Query(None, description="Filter: 紧急/重要/关注/一般"),
    min_relevance: int | None = Query(None, ge=0, le=100, description="Min relevance score"),
    keyword: str | None = Query(None, description="Search in name/position/department/note"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get LLM-enriched personnel changes with relevance analysis and action suggestions."""
    return personnel_service.get_enriched_feed(
        group=group,
        importance=importance,
        min_relevance=min_relevance,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )


@router.get("/enriched-stats", response_model=PersonnelEnrichedStatsResponse)
async def get_enriched_stats():
    """Get summary statistics for LLM-enriched personnel data."""
    return personnel_service.get_enriched_stats()
