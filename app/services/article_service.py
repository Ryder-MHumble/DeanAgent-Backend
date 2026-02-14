from __future__ import annotations

import math

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.schemas.article import ArticleSearchParams, ArticleUpdate
from app.schemas.common import PaginatedResponse

_ALLOWED_SORT_FIELDS = {"crawled_at", "published_at", "title", "importance"}


async def list_articles(
    db: AsyncSession, params: ArticleSearchParams
) -> PaginatedResponse:
    """List articles with filtering, sorting, and pagination."""
    query = select(Article)

    # Filters
    if params.dimension:
        query = query.where(Article.dimension == params.dimension)
    if params.source_id:
        query = query.where(Article.source_id == params.source_id)
    if params.keyword:
        pattern = f"%{params.keyword}%"
        query = query.where(Article.title.ilike(pattern) | Article.summary.ilike(pattern))
    if params.tags:
        query = query.where(Article.tags.overlap(params.tags))
    if params.date_from:
        query = query.where(Article.published_at >= params.date_from)
    if params.date_to:
        query = query.where(Article.published_at <= params.date_to)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sorting (whitelist to prevent arbitrary column access)
    sort_field = params.sort_by if params.sort_by in _ALLOWED_SORT_FIELDS else "crawled_at"
    sort_column = getattr(Article, sort_field)
    if params.order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # Pagination
    offset = (params.page - 1) * params.page_size
    query = query.offset(offset).limit(params.page_size)

    result = await db.execute(query)
    articles = result.scalars().all()

    return PaginatedResponse(
        items=articles,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=math.ceil(total / params.page_size) if params.page_size else 0,
    )


async def get_article(db: AsyncSession, article_id: int) -> Article | None:
    result = await db.execute(select(Article).where(Article.id == article_id))
    return result.scalar_one_or_none()


async def update_article(
    db: AsyncSession, article_id: int, data: ArticleUpdate
) -> Article | None:
    values = data.model_dump(exclude_unset=True)
    if not values:
        return await get_article(db, article_id)
    await db.execute(update(Article).where(Article.id == article_id).values(**values))
    await db.commit()
    return await get_article(db, article_id)


async def get_article_stats(
    db: AsyncSession, group_by: str = "dimension"
) -> list[dict]:
    """Get article counts grouped by dimension, source, or day."""
    if group_by == "source":
        col = Article.source_id
    elif group_by == "day":
        col = func.date(Article.crawled_at)
    else:
        col = Article.dimension

    query = select(col.label("group"), func.count().label("count")).group_by(col).order_by(
        func.count().desc()
    )
    result = await db.execute(query)
    return [{"group": str(row.group), "count": row.count} for row in result.fetchall()]
