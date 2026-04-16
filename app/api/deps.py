from fastapi import HTTPException, Query
from pydantic import ValidationError

from app.schemas.article import ArticleSearchParams


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def get_article_search_params(
    dimension: str | None = Query(None, description="Filter by dimension"),
    source_id_filter: str | None = Query(
        None,
        alias="source_id",
        description="按单个信源 ID 筛选（精确匹配）",
    ),
    source_ids: str | None = Query(None, description="按多个信源 ID 筛选（逗号分隔，精确匹配）"),
    source_name: str | None = Query(None, description="按单个信源名称筛选（模糊匹配）"),
    source_names: str | None = Query(None, description="按多个信源名称筛选（逗号分隔，模糊匹配）"),
    keyword: str | None = Query(None, description="Keyword filter in title/content"),
    date_from: str | None = Query(None, description="Start date (ISO format)"),
    date_to: str | None = Query(None, description="End date (ISO format)"),
    sort_by: str = Query("crawled_at", description="Sort field"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    custom_field_key: str | None = Query(None, description="按自定义字段 key 过滤"),
    custom_field_value: str | None = Query(
        None, description="自定义字段 value（需配合 custom_field_key）"
    ),
) -> ArticleSearchParams:
    try:
        return ArticleSearchParams(
            dimension=_normalize_optional_text(dimension),
            source_id=_normalize_optional_text(source_id_filter),
            source_ids=_normalize_optional_text(source_ids),
            source_name=_normalize_optional_text(source_name),
            source_names=_normalize_optional_text(source_names),
            keyword=_normalize_optional_text(keyword),
            date_from=_normalize_optional_text(date_from),
            date_to=_normalize_optional_text(date_to),
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
            custom_field_key=_normalize_optional_text(custom_field_key),
            custom_field_value=_normalize_optional_text(custom_field_value),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
