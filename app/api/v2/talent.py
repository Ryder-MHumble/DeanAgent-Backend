"""Talent Radar API endpoints."""
from datetime import date

from fastapi import APIRouter, Query

from app.schemas.business.talent import TalentListResponse
from app.services.business.talent_service import get_talent_list

router = APIRouter()


@router.get("/index", response_model=TalentListResponse)
async def list_talent(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Get talent-related articles and data."""
    return get_talent_list(date_from=date_from, date_to=date_to, limit=limit)
