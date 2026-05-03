from fastapi import APIRouter

from app.api.academic import (
    events,
    institutions,
    papers,
    projects,
    scholars,
    students,
    university_leadership,
    venues,
)
from app.api.content import articles, dimensions, sources
from app.api.external import aminer
from app.api.intel.router import intel_router
from app.api.operations import crawler_control, health, llm_tracking
from app.api.reports import reports
from app.api.social import sentiment, social_kol, social_posts


def build_api_router(prefix: str = "/api") -> APIRouter:
    router = APIRouter(prefix=prefix)

    router.include_router(articles.router, prefix="/articles", tags=["articles"])
    router.include_router(sources.router, prefix="/sources", tags=["sources"])
    router.include_router(crawler_control.router, prefix="/crawler", tags=["crawler-control"])
    router.include_router(health.router, prefix="/health", tags=["health"])
    router.include_router(dimensions.router, prefix="/dimensions", tags=["dimensions"])
    router.include_router(intel_router, prefix="/intel", tags=["intel"])
    router.include_router(sentiment.router, prefix="/sentiment", tags=["sentiment"])
    router.include_router(social_kol.router, prefix="/social-kol", tags=["social-kol"])
    router.include_router(social_posts.router, prefix="/social-posts", tags=["social-posts"])
    router.include_router(reports.router, tags=["reports"])
    router.include_router(llm_tracking.router)
    router.include_router(scholars.router, prefix="/scholars", tags=["scholars"])
    router.include_router(students.router, prefix="/students", tags=["students"])
    router.include_router(events.router, prefix="/events", tags=["events"])
    router.include_router(aminer.router, prefix="/aminer", tags=["aminer"])
    router.include_router(projects.router, prefix="/projects", tags=["projects"])
    router.include_router(venues.router, prefix="/venues", tags=["venues"])
    router.include_router(papers.router, tags=["papers"])
    router.include_router(
        university_leadership.router,
        prefix="/leadership",
        tags=["leadership"],
    )
    # institutions.router 包含 /{institution_id} 通配符路由，必须最后注册
    router.include_router(institutions.router, prefix="/institutions", tags=["institutions"])
    return router


api_router = build_api_router(prefix="/api")
legacy_v1_router = build_api_router(prefix="/api/v1")
