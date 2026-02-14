from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article

DIMENSION_NAMES = {
    "national_policy": "对国家",
    "beijing_policy": "对北京",
    "technology": "对技术",
    "talent": "对人才",
    "industry": "对产业",
    "sentiment": "对学院舆情",
    "universities": "对高校",
    "events": "对日程",
    "personnel": "对人事",
}


async def list_dimensions(db: AsyncSession) -> list[dict]:
    """List all dimensions with article counts and last updated timestamps."""
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
