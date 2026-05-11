from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db.pool import get_pool
from app.schemas.openreview_author import (
    OpenReviewAuthorListResponse,
    OpenReviewAuthorProfile,
)
from app.services import openreview_author_service

router = APIRouter()


@router.get(
    "",
    response_model=OpenReviewAuthorListResponse,
    summary="OpenReview author list",
)
async def list_openreview_authors(
    q: str | None = Query(default=None),
    university: str | None = Query(default=None),
    department: str | None = Query(default=None),
    crawl_status: str | None = Query(default=None),
    min_publication_count: int | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="publication_count"),
    order: str = Query(default="desc"),
) -> OpenReviewAuthorListResponse:
    payload = await openreview_author_service.list_openreview_authors(
        get_pool(),
        q=q,
        university=university,
        department=department,
        crawl_status=crawl_status,
        min_publication_count=min_publication_count,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        order=order,
    )
    return OpenReviewAuthorListResponse(**payload)


@router.get(
    "/{profile_id}",
    response_model=OpenReviewAuthorProfile,
    summary="OpenReview author detail",
)
async def get_openreview_author(profile_id: str) -> OpenReviewAuthorProfile:
    record = await openreview_author_service.get_openreview_author(get_pool(), profile_id)
    if record is None:
        raise HTTPException(status_code=404, detail="openreview author not found")
    return OpenReviewAuthorProfile(**record)
