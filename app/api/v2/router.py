"""V2 API router - business-level endpoints."""
from fastapi import APIRouter

from app.api.v2 import briefing, events, kol, policy, talent, tech, university

v2_router = APIRouter(prefix="/api/v2")

v2_router.include_router(policy.router, prefix="/policy", tags=["policy"])
v2_router.include_router(tech.router, prefix="/tech", tags=["tech"])
v2_router.include_router(university.router, prefix="/university", tags=["university"])
v2_router.include_router(talent.router, prefix="/talent", tags=["talent"])
v2_router.include_router(events.router, prefix="/events", tags=["events"])
v2_router.include_router(briefing.router, prefix="/briefing", tags=["briefing"])
v2_router.include_router(kol.router, prefix="/kol", tags=["kol"])
