from __future__ import annotations

from pydantic import BaseModel, Field


class PublicationWriteRequest(BaseModel):
    owner_type: str
    owner_id: str
    title: str
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    publication_date: str | None = None
    authors: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    project_group_name: str | None = None
    source_type: str | None = None
    source_details: dict = Field(default_factory=dict)
    compliance_details: dict = Field(default_factory=dict)
    confirmed_by: str | None = None


class PublicationOwnerPatchRequest(BaseModel):
    title: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    publication_date: str | None = None
    authors: list[str] | None = None
    affiliations: list[str] | None = None
    project_group_name: str | None = None
    source_type: str | None = None
    source_details: dict | None = None
    compliance_details: dict | None = None
    confirmed_by: str | None = None


class CandidateConfirmRequest(BaseModel):
    confirmed_by: str | None = None


class CandidateRejectRequest(BaseModel):
    rejected_by: str | None = None
    note: str | None = None


class PublicationListItem(BaseModel):
    paper_uid: str
    owner_link_id: str
    publication_id: str
    owner_type: str
    owner_id: str
    canonical_uid: str
    title: str
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    publication_date: str | None = None
    authors: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    project_group_name: str | None = None
    source: str | None = None
    source_details: dict = Field(default_factory=dict)
    compliance_details: dict = Field(default_factory=dict)
    affiliation_status: str | None = None
    compliance_reason: str | None = None
    matched_tokens: list[str] = Field(default_factory=list)
    checked_affiliations: list[str] = Field(default_factory=list)
    assessed_at: str | None = None
    confirmed_by: str | None = None
    confirmed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PublicationListResponse(BaseModel):
    items: list[PublicationListItem]
    total: int


class PublicationWriteResponse(BaseModel):
    status: str
    publication_id: str
    owner_link_id: str


class PublicationBulkImportRequest(BaseModel):
    items: list[PublicationWriteRequest] = Field(default_factory=list)


class PublicationBulkImportResponse(BaseModel):
    items: list[PublicationWriteResponse]
    total: int


class PublicationCandidateItem(BaseModel):
    candidate_id: str
    owner_type: str
    owner_id: str
    target_key: str | None = None
    canonical_uid: str
    title: str
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    publication_date: str | None = None
    authors: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    source_type: str
    source_details: dict = Field(default_factory=dict)
    project_group_name: str | None = None
    compliance_details: dict = Field(default_factory=dict)
    review_status: str
    review_decision: dict = Field(default_factory=dict)
    promoted_publication_id: str | None = None
    promoted_owner_link_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PublicationCandidateListResponse(BaseModel):
    items: list[PublicationCandidateItem]
    total: int


class PublicationCandidateConfirmResponse(BaseModel):
    status: str
    candidate_id: str
    publication_id: str
    owner_link_id: str


class PublicationCandidateRejectResponse(BaseModel):
    status: str
    candidate_id: str

