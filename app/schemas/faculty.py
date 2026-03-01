"""Pydantic schemas for the Faculty API (/api/v1/faculty/)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field  # noqa: F401

# ---------------------------------------------------------------------------
# List item (lightweight, for GET /faculty/)
# ---------------------------------------------------------------------------


class FacultyListItem(BaseModel):
    """Single row in the faculty list — key fields only."""

    url_hash: str = Field(description="师资唯一 ID (url_hash of profile_url)")
    name: str = Field(description="中文姓名")
    name_en: str = Field(default="", description="英文姓名")
    photo_url: str = Field(default="", description="照片 URL")
    university: str = Field(default="", description="所属大学")
    department: str = Field(default="", description="所属院系")
    position: str = Field(default="", description="职称")
    academic_titles: list[str] = Field(default_factory=list, description="学术头衔（杰青/院士等）")
    is_academician: bool = Field(default=False, description="是否院士")
    research_areas: list[str] = Field(default_factory=list, description="研究方向")
    email: str = Field(default="", description="邮箱")
    profile_url: str = Field(default="", description="个人主页 URL")
    source_id: str = Field(default="", description="信源 ID")
    group: str = Field(default="", description="信源分组（高校名缩写）")
    data_completeness: int = Field(default=0, description="数据完整度 0–100")
    # User-managed fields (merged from annotations)
    is_potential_recruit: bool = Field(default=False, description="潜在招募对象")
    is_advisor_committee: bool = Field(default=False, description="顾问委员会成员")
    is_adjunct_supervisor: bool = Field(default=False, description="兼职导师")
    crawled_at: str = Field(default="", description="最后爬取时间 ISO8601")


class FacultyListResponse(BaseModel):
    """Response for GET /faculty/."""

    total: int = Field(description="符合条件的总师资数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
    total_pages: int = Field(description="总页数")
    items: list[FacultyListItem]


# ---------------------------------------------------------------------------
# Education / DynamicUpdate sub-models (mirrors scholar.py for API output)
# ---------------------------------------------------------------------------


class EducationRecordOut(BaseModel):
    degree: str = ""
    institution: str = ""
    year: str = ""
    major: str = ""


class DynamicUpdateOut(BaseModel):
    update_type: str = ""
    title: str = ""
    content: str = ""
    source_url: str = ""
    published_at: str = ""
    crawled_at: str = ""
    added_by: str = ""


# ---------------------------------------------------------------------------
# Detail response (full ScholarRecord + user annotations merged)
# ---------------------------------------------------------------------------


class FacultyDetailResponse(BaseModel):
    """Full faculty record: crawled fields + user annotations merged."""

    # Identity
    url_hash: str
    source_id: str
    group: str
    # Basic
    name: str
    name_en: str
    gender: str
    photo_url: str
    # Affiliation
    university: str
    department: str
    secondary_departments: list[str]
    # Title
    position: str
    academic_titles: list[str]
    is_academician: bool
    # Research
    research_areas: list[str]
    keywords: list[str]
    bio: str
    bio_en: str
    # Contact
    email: str
    phone: str
    office: str
    # URLs
    profile_url: str
    lab_url: str
    google_scholar_url: str
    dblp_url: str
    orcid: str
    # Education
    phd_institution: str
    phd_year: str
    education: list[EducationRecordOut]
    # Metrics
    publications_count: int
    h_index: int
    citations_count: int
    metrics_updated_at: str
    # Institute relations [user-managed]
    is_advisor_committee: bool
    is_adjunct_supervisor: bool
    supervised_students: list[str]
    joint_research_projects: list[str]
    joint_management_roles: list[str]
    academic_exchange_records: list[str]
    is_potential_recruit: bool
    institute_relation_notes: str
    relation_updated_by: str
    relation_updated_at: str
    # Dynamic updates (crawler + user)
    recent_updates: list[DynamicUpdateOut]
    # Meta
    source_url: str
    crawled_at: str
    first_seen_at: str
    last_seen_at: str
    is_active: bool
    data_completeness: int


# ---------------------------------------------------------------------------
# Source item (for GET /faculty/sources)
# ---------------------------------------------------------------------------


class FacultySourceItem(BaseModel):
    id: str
    name: str
    group: str
    university: str
    department: str
    is_enabled: bool
    item_count: int
    last_crawl_at: str | None


class FacultySourcesResponse(BaseModel):
    total: int
    items: list[FacultySourceItem]


# ---------------------------------------------------------------------------
# Stats response (for GET /faculty/stats)
# ---------------------------------------------------------------------------


class FacultyStatsResponse(BaseModel):
    total: int = Field(description="总师资数")
    academicians: int = Field(description="院士数")
    potential_recruits: int = Field(description="潜在招募对象数")
    advisor_committee: int = Field(description="顾问委员会成员数")
    adjunct_supervisors: int = Field(description="兼职导师数")
    by_university: list[dict[str, Any]] = Field(
        description="按高校统计 [{university, count}]"
    )
    by_position: list[dict[str, Any]] = Field(
        description="按职称统计 [{position, count}]"
    )
    completeness_buckets: dict[str, int] = Field(
        description="完整度分布 {<30, 30-60, 60-80, >80}"
    )
    sources_count: int = Field(description="信源数量")


# ---------------------------------------------------------------------------
# Write request schemas
# ---------------------------------------------------------------------------


class InstituteRelationUpdate(BaseModel):
    """PATCH /faculty/{url_hash}/relation — all fields optional."""

    is_advisor_committee: bool | None = Field(default=None, description="顾问委员会成员")
    is_adjunct_supervisor: bool | None = Field(default=None, description="兼职导师")
    supervised_students: list[str] | None = Field(default=None, description="指导学生列表")
    joint_research_projects: list[str] | None = Field(default=None, description="联合科研项目列表")
    joint_management_roles: list[str] | None = Field(
        default=None, description="在两院联合管理职务列表"
    )
    academic_exchange_records: list[str] | None = Field(
        default=None, description="学术交流活动记录列表"
    )
    is_potential_recruit: bool | None = Field(default=None, description="潜在招募对象")
    institute_relation_notes: str | None = Field(default=None, description="补充备注（自由文本）")
    relation_updated_by: str | None = Field(default=None, description="更新人")


class UserUpdateCreate(BaseModel):
    """POST /faculty/{url_hash}/updates — add a user-authored dynamic update."""

    update_type: Literal[
        "major_project", "talent_title", "position_change", "award", "publication", "other"
    ] = Field(description="动态类型")
    title: str = Field(description="标题/摘要")
    content: str = Field(default="", description="详细内容")
    source_url: str = Field(default="", description="来源链接（可选）")
    published_at: str = Field(default="", description="事件时间 YYYY-MM-DD 或 ISO8601（可选）")
    added_by: str = Field(description="录入人（用户名），系统自动补充为 'user:{added_by}'")
