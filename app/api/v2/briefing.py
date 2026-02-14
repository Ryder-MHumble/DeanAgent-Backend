"""Home Briefing API endpoints (daily summary, metrics, priorities)."""
from fastapi import APIRouter, Query

from app.schemas.business.briefing import (
    DailySummaryResponse,
    MetricsResponse,
    PriorityResponse,
)
from app.services.business.briefing_service import (
    get_daily_summary,
    get_metrics,
    get_priorities,
)

router = APIRouter()


@router.get("/metrics", response_model=MetricsResponse)
async def dashboard_metrics():
    """Get dashboard metric cards for all dimensions."""
    return get_metrics()


@router.get("/priorities", response_model=PriorityResponse)
async def priority_items(
    limit: int = Query(10, ge=1, le=50),
):
    """Get priority items across all dimensions."""
    return get_priorities(limit=limit)


@router.get("/daily", response_model=DailySummaryResponse)
async def daily_summary():
    """Generate AI daily summary (requires LLM)."""
    return await get_daily_summary()
