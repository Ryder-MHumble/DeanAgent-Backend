from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_article_search_params, get_db_session
from app.schemas.article import (
    ArticleBrief,
    ArticleDetail,
    ArticleSearchParams,
    ArticleStats,
    ArticleUpdate,
)
from app.schemas.common import PaginatedResponse
from app.services import article_service

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[ArticleBrief])
async def list_articles(
    params: ArticleSearchParams = Depends(get_article_search_params),
    db: AsyncSession = Depends(get_db_session),
):
    """List articles with filtering, sorting, and pagination."""
    return await article_service.list_articles(db, params)


@router.get("/search", response_model=PaginatedResponse[ArticleBrief])
async def search_articles(
    params: ArticleSearchParams = Depends(get_article_search_params),
    db: AsyncSession = Depends(get_db_session),
):
    """Full-text search across articles."""
    return await article_service.list_articles(db, params)


@router.get("/stats", response_model=list[ArticleStats])
async def get_stats(
    group_by: str = "dimension",
    db: AsyncSession = Depends(get_db_session),
):
    """Get aggregated article statistics."""
    return await article_service.get_article_stats(db, group_by)


@router.get("/{article_id}", response_model=ArticleDetail)
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """Get a single article with full content."""
    article = await article_service.get_article(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.patch("/{article_id}", response_model=ArticleDetail)
async def update_article(
    article_id: int,
    data: ArticleUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update article metadata (mark read, set importance)."""
    article = await article_service.update_article(db, article_id, data)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
