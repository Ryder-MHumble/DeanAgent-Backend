from datetime import datetime

from pydantic import BaseModel


class ArticleBrief(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    source_id: str
    dimension: str
    url: str
    title: str
    summary: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    crawled_at: datetime
    tags: list[str] = []
    is_read: bool = False
    importance: int | None = None


class ArticleDetail(ArticleBrief):
    content: str | None = None
    extra: dict = {}


class ArticleUpdate(BaseModel):
    is_read: bool | None = None
    importance: int | None = None


class ArticleSearchParams(BaseModel):
    q: str | None = None
    dimension: str | None = None
    source_id: str | None = None
    tags: list[str] | None = None
    keyword: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    sort_by: str = "crawled_at"
    order: str = "desc"
    page: int = 1
    page_size: int = 20


class ArticleStats(BaseModel):
    group: str
    count: int
