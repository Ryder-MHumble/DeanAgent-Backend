"""Pydantic schemas for global student management endpoints."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StudentListItem(BaseModel):
    """Student item returned by list endpoint (optimized fields)."""

    id: str
    scholar_id: str = ""
    student_no: str = ""
    name: str
    home_university: str = ""
    institution: str = Field(default="", description="[兼容] 等价于 home_university")
    enrollment_year: str = ""
    status: str = "在读"
    email: str = ""
    phone: str = ""
    major: str = ""
    mentor_name: str = ""


class StudentDetailResponse(StudentListItem):
    """Student detail response with additional editable metadata."""

    degree_type: str = ""
    expected_graduation_year: str = ""
    entry_date: str = ""
    paper_date_floor: str = ""
    notes: str = ""
    added_by: str = ""
    created_at: str = ""
    updated_at: str = ""


class StudentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None = None
    items: list[StudentListItem]


class StudentCreateRequest(BaseModel):
    scholar_id: str | None = Field(
        default=None,
        description="关联学者 url_hash；为空时自动挂载到占位导师",
    )
    mentor_name: str = Field(default="", description="导师姓名（可为空）")
    student_no: str = Field(default="", description="学号")
    name: str = Field(description="学生姓名")
    home_university: str = Field(default="", description="共建高校/学籍学校")
    institution: str = Field(default="", description="[兼容] 共建高校/学籍学校，等价于 home_university")
    major: str = Field(default="", description="专业")
    degree_type: str = Field(default="", description="培养类型")
    enrollment_year: str = Field(default="", description="年级/入学年份")
    expected_graduation_year: str = Field(default="", description="预计毕业年份")
    entry_date: str = Field(default="", description="入项时间")
    paper_date_floor: str = Field(default="", description="论文时间下限")
    status: str = Field(default="在读", description="状态")
    email: str = Field(default="", description="邮箱")
    phone: str = Field(default="", description="电话")
    notes: str = Field(default="", description="备注")
    added_by: str = Field(default="", description="录入人")


class StudentUpdateRequest(BaseModel):
    scholar_id: str | None = Field(default=None, description="关联学者 url_hash")
    mentor_name: str | None = Field(default=None, description="导师姓名")
    student_no: str | None = Field(default=None, description="学号")
    name: str | None = Field(default=None, description="学生姓名")
    home_university: str | None = Field(default=None, description="共建高校/学籍学校")
    institution: str | None = Field(default=None, description="[兼容] 共建高校/学籍学校，等价于 home_university")
    major: str | None = Field(default=None, description="专业")
    degree_type: str | None = Field(default=None, description="培养类型")
    enrollment_year: str | None = Field(default=None, description="年级/入学年份")
    expected_graduation_year: str | None = Field(default=None, description="预计毕业年份")
    entry_date: str | None = Field(default=None, description="入项时间")
    paper_date_floor: str | None = Field(default=None, description="论文时间下限")
    status: str | None = Field(default=None, description="状态")
    email: str | None = Field(default=None, description="邮箱")
    phone: str | None = Field(default=None, description="电话")
    notes: str | None = Field(default=None, description="备注")
    updated_by: str | None = Field(default=None, description="更新人")


class StudentFilterOptions(BaseModel):
    grades: list[str] = Field(default_factory=list)
    universities: list[str] = Field(default_factory=list)
    mentors: list[str] = Field(default_factory=list)


class StudentPaperRecord(BaseModel):
    paper_uid: str
    title: str
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    publication_date: str | None = None
    source: str | None = None
    authors: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    created_at: str | None = None


class StudentPapersResponse(BaseModel):
    items: list[StudentPaperRecord]
    total: int


class StudentPaperUpsertRequest(BaseModel):
    title: str
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    publication_date: str | None = None
    source: str | None = None
    authors: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)


class StudentPaperComplianceRequest(BaseModel):
    note: str | None = None


class StudentPaperWriteResponse(BaseModel):
    status: str
    paper_uid: str


class StudentPublicationCandidateRecord(BaseModel):
    candidate_id: str
    target_key: str | None = None
    owner_type: str
    owner_id: str
    canonical_uid: str
    paper_uid: str | None = None
    title: str
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    publication_date: str | None = None
    source: str | None = None
    source_type: str | None = None
    source_details: dict[str, Any] = Field(default_factory=dict)
    authors: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    review_status: str
    review_decision: dict[str, Any] = Field(default_factory=dict)
    compliance_details: dict[str, Any] = Field(default_factory=dict)
    affiliation_status: str | None = None
    compliance_reason: str | None = None
    matched_tokens: list[str] = Field(default_factory=list)
    checked_affiliations: list[str] = Field(default_factory=list)
    assessed_at: str | None = None
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class StudentPublicationWorkspaceCounts(BaseModel):
    confirmed: int = 0
    pending_review: int = 0
    rejected: int = 0


class StudentPublicationWorkspaceResponse(BaseModel):
    counts: StudentPublicationWorkspaceCounts
    confirmed_publications: list[StudentPaperRecord] = Field(default_factory=list)
    pending_candidates: list[StudentPublicationCandidateRecord] = Field(default_factory=list)
    rejected_candidates: list[StudentPublicationCandidateRecord] = Field(default_factory=list)


class StudentPublicationCandidatePatchRequest(BaseModel):
    title: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    publication_date: str | None = None
    source: str | None = None
    authors: list[str] | None = None
    affiliations: list[str] | None = None


class StudentPublicationCandidateDecisionRequest(BaseModel):
    reviewed_by: str | None = None
    note: str | None = None
    affiliation_status: str | None = None
    compliance_reason: str | None = None
    matched_tokens: list[str] | None = None
    checked_affiliations: list[str] | None = None
    compliance_details: dict[str, Any] | None = None


class StudentPublicationCandidateActionResponse(BaseModel):
    status: str
    candidate_id: str
    paper_uid: str | None = None
