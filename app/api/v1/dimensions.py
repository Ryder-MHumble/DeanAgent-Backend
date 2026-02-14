from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.article import Article
from app.schemas.article import ArticleBrief, ArticleSearchParams
from app.schemas.common import PaginatedResponse
from app.services import article_service

router = APIRouter()

DIMENSION_NAMES = {
    "national_policy": "对国家",
    "beijing_policy": "对北京",
    "technology": "对技术",
    "talent": "对人才",
    "industry": "对产业",
    "sentiment": "对学院舆情",
    "universities": "对高校",
    "events": "对日程",
}


@router.get("/")
async def list_dimensions(db: AsyncSession = Depends(get_db_session)):
    """List all 8 dimensions with article counts and last updated timestamps."""
    query = select(
        Article.dimension,
        func.count().label("article_count"),
        func.max(Article.crawled_at).label("last_updated"),
    ).group_by(Article.dimension)
    result = await db.execute(query)

    rows = result.fetchall()

    dimensions = []
    found = set()
    for row in rows:
        found.add(row.dimension)
        dimensions.append(
            {
                "id": row.dimension,
                "name": DIMENSION_NAMES.get(row.dimension, row.dimension),
                "article_count": row.article_count,
                "last_updated": row.last_updated,
            }
        )

    # Include dimensions with zero articles
    for dim_id, dim_name in DIMENSION_NAMES.items():
        if dim_id not in found:
            dimensions.append(
                {
                    "id": dim_id,
                    "name": dim_name,
                    "article_count": 0,
                    "last_updated": None,
                }
            )

    dim_order = list(DIMENSION_NAMES.keys())
    return sorted(
        dimensions,
        key=lambda d: dim_order.index(d["id"]) if d["id"] in dim_order else len(dim_order),
    )


@router.get("/{dimension}", response_model=PaginatedResponse[ArticleBrief])
async def get_dimension_articles(
    dimension: str,
    keyword: str | None = Query(None),
    sort_by: str = Query("crawled_at"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
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
