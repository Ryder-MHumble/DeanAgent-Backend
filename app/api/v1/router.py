from fastapi import APIRouter

from app.api.v1 import articles, dimensions, health, sources
from app.api.v1.intel.router import intel_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(articles.router, prefix="/articles", tags=["articles"])
v1_router.include_router(sources.router, prefix="/sources", tags=["sources"])
v1_router.include_router(health.router, prefix="/health", tags=["health"])
v1_router.include_router(dimensions.router, prefix="/dimensions", tags=["dimensions"])
v1_router.include_router(intel_router, prefix="/intel", tags=["intel"])
