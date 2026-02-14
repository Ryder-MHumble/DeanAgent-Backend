"""KOL Tracking API endpoints (powered by Twitter API)."""
from fastapi import APIRouter, Query

from app.schemas.business.kol import KOLListResponse, KOLTweetsResponse
from app.services.business.kol_service import get_kol_profiles, get_kol_tweets

router = APIRouter()


@router.get("/profiles", response_model=KOLListResponse)
async def list_kol_profiles():
    """Get tracked AI KOL profiles from Twitter."""
    return await get_kol_profiles()


@router.get("/tweets", response_model=KOLTweetsResponse)
async def list_kol_tweets(
    username: str | None = Query(None, description="Filter by specific username"),
    limit: int = Query(30, ge=1, le=100),
):
    """Get recent tweets from tracked AI KOLs."""
    return await get_kol_tweets(username=username, limit=limit)
