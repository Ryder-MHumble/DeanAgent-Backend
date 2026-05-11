from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

JsonObjectOrArray = dict[str, Any] | list[Any]


class OpenReviewAuthorProfile(BaseModel):
    profile_id: str
    profile_url: str | None = None
    canonical_profile_id: str | None = None
    requested_profile_ids: list[str] = Field(default_factory=list)
    preferred_name: str | None = None
    names: list[Any] = Field(default_factory=list)
    preferred_email: str | None = None
    emails: list[str] = Field(default_factory=list)
    personal_links: JsonObjectOrArray = Field(default_factory=list)
    homepage_url: str | None = None
    google_scholar_url: str | None = None
    dblp_url: str | None = None
    linkedin_url: str | None = None
    orcid: str | None = None
    semantic_scholar_url: str | None = None
    current_affiliation: JsonObjectOrArray = Field(default_factory=dict)
    university: str | None = None
    department: str | None = None
    position: str | None = None
    career_history: JsonObjectOrArray = Field(default_factory=list)
    education: JsonObjectOrArray = Field(default_factory=list)
    expertise: JsonObjectOrArray = Field(default_factory=dict)
    keywords: list[str] = Field(default_factory=list)
    relations: JsonObjectOrArray = Field(default_factory=dict)
    publications: JsonObjectOrArray = Field(default_factory=list)
    publication_count: int = 0
    source_author_rows: JsonObjectOrArray = Field(default_factory=list)
    raw_profile: JsonObjectOrArray | None = None
    raw_publication_notes: JsonObjectOrArray | None = None
    crawl_status: str | None = None
    crawl_error: str | None = None
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    crawled_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class OpenReviewAuthorListResponse(BaseModel):
    items: list[OpenReviewAuthorProfile]
    total: int
    page: int = 1
    page_size: int = 20
