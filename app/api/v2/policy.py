"""Policy Intelligence API endpoints."""
from datetime import date

from fastapi import APIRouter, Query

from app.schemas.business.policy import PolicyListResponse
from app.services.business.policy_service import (
    get_policy_list,
    get_policy_list_enhanced,
)

router = APIRouter()


@router.get("/national", response_model=PolicyListResponse)
async def list_national_policies(
    date_from: date | None = Query(None, description="Start date filter"),
    date_to: date | None = Query(None, description="End date filter"),
    limit: int = Query(50, ge=1, le=200),
    enhanced: bool = Query(False, description="Enable LLM enhancement"),
):
    """List national policy articles."""
    if enhanced:
        return await get_policy_list_enhanced(
            "national_policy", date_from=date_from, date_to=date_to, limit=limit,
        )
    return get_policy_list(
        "national_policy", date_from=date_from, date_to=date_to, limit=limit,
    )


@router.get("/beijing", response_model=PolicyListResponse)
async def list_beijing_policies(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    enhanced: bool = Query(False, description="Enable LLM enhancement"),
):
    """List Beijing policy articles."""
    if enhanced:
        return await get_policy_list_enhanced(
            "beijing_policy", date_from=date_from, date_to=date_to, limit=limit,
        )
    return get_policy_list(
        "beijing_policy", date_from=date_from, date_to=date_to, limit=limit,
    )
