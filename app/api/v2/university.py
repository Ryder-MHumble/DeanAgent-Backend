"""University Ecosystem API endpoints."""
from datetime import date

from fastapi import APIRouter, Query

from app.schemas.business.university import (
    PeerListResponse,
    PersonnelListResponse,
    ResearchListResponse,
)
from app.services.business.university_service import (
    get_peer_dynamics,
    get_personnel_changes,
    get_research_outputs,
)

router = APIRouter()


@router.get("/peers", response_model=PeerListResponse)
async def list_peer_dynamics(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    """Get peer institution dynamics (grouped by institution)."""
    return get_peer_dynamics(date_from=date_from, date_to=date_to)


@router.get("/personnel", response_model=PersonnelListResponse)
async def list_personnel_changes(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Get personnel changes from universities."""
    return get_personnel_changes(date_from=date_from, date_to=date_to, limit=limit)


@router.get("/research", response_model=ResearchListResponse)
async def list_research_outputs(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Get research outputs (papers, patents, awards)."""
    return get_research_outputs(date_from=date_from, date_to=date_to, limit=limit)
