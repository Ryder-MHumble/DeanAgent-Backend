from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.article import ArticleBrief, ArticleSearchParams
from app.schemas.common import PaginatedResponse
from app.services import article_service, dimension_service

router = APIRouter()


@router.get("/")
async def list_dimensions(db: AsyncSession = Depends(get_db)):
    """List all 9 dimensions with article counts and last updated timestamps."""
    return await dimension_service.list_dimensions(db)


@router.get("/{dimension}", response_model=PaginatedResponse[ArticleBrief])
async def get_dimension_articles(
    dimension: str,
    keyword: str | None = Query(None),
    sort_by: str = Query("crawled_at"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get articles for a specific dimension."""
    params = ArticleSearchParams(
        dimension=dimension,
        keyword=keyword,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )
    return await article_service.list_articles(db, params)
