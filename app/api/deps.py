from fastapi import Query

from app.schemas.article import ArticleSearchParams


def get_article_search_params(
    dimension: str | None = Query(None, description="Filter by dimension"),
    source_id: str | None = Query(None, description="Filter by source ID"),
    keyword: str | None = Query(None, description="Keyword filter in title/content"),
    date_from: str | None = Query(None, description="Start date (ISO format)"),
    date_to: str | None = Query(None, description="End date (ISO format)"),
    sort_by: str = Query("crawled_at", description="Sort field"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> ArticleSearchParams:
    return ArticleSearchParams(
        dimension=dimension,
        source_id=source_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )
