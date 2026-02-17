"""Intel sub-router — aggregates all business intelligence endpoints."""
from fastapi import APIRouter

from app.api.v1.intel import personnel, policy

intel_router = APIRouter()

intel_router.include_router(policy.router, prefix="/policy", tags=["policy-intel"])
intel_router.include_router(personnel.router, prefix="/personnel", tags=["personnel-intel"])
