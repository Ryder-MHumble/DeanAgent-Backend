"""Events/Schedule API endpoints."""
from datetime import date

from fastapi import APIRouter, Query

from app.schemas.business.events import EventListResponse
from app.services.business.events_service import get_events_list

router = APIRouter()


@router.get("/recommended", response_model=EventListResponse)
async def list_events(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Get recommended events and conferences."""
    return get_events_list(date_from=date_from, date_to=date_to, limit=limit)
