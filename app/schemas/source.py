from datetime import datetime

from pydantic import BaseModel


class SourceResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    url: str
    dimension: str
    crawl_method: str
    schedule: str
    is_enabled: bool
    priority: int
    last_crawl_at: datetime | None = None
    last_success_at: datetime | None = None
    consecutive_failures: int = 0


class SourceUpdate(BaseModel):
    is_enabled: bool | None = None
