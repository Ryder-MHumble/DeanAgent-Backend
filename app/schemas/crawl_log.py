from datetime import datetime

from pydantic import BaseModel


class CrawlLogResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    source_id: str
    status: str
    items_total: int
    items_new: int
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None


class CrawlHealthResponse(BaseModel):
    total_sources: int
    enabled_sources: int
    healthy: int
    warning: int
    failing: int
    last_24h_crawls: int
    last_24h_new_articles: int
