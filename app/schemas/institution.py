"""Pydantic schemas for the Institution API (/api/v1/institutions/)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------


class ScholarInfo(BaseModel):
    """学者信息（校领导/重要学者）"""

    name: str = Field(description="姓名")
    title: str | None = Field(default=None, description="头衔（院士/校长/书记等）")
    department: str | None = Field(default=None, description="所属院系")
    research_area: str | None = Field(default=None, description="研究方向")


class MentorInfo(BaseModel):
    """共建导师信息"""

    name: str | None = Field(default=None, description="姓名")
    category: str | None = Field(default=None, description="类别（教学研究等）")
    department: str | None = Field(default=None, description="所属院系")


class DepartmentSource(BaseModel):
    """院系信源信息"""

    source_id: str = Field(description="信源 ID")
    source_name: str = Field(description="信源名称")
    scholar_count: int = Field(default=0, description="学者数量")
    is_enabled: bool = Field(default=True, description="是否启用")
    last_crawl_at: str | None = Field(default=None, description="最后爬取时间")


class DepartmentInfo(BaseModel):
    """院系信息"""

    id: str = Field(description="院系 ID")
    name: str = Field(description="院系名称")
    scholar_count: int = Field(default=0, description="学者数量")
    sources: list[DepartmentSource] = Field(default_factory=list, description="信源列表")
    org_name: str | None = Field(default=None, description="AMiner 标准化机构名（院系级别）")


# ---------------------------------------------------------------------------
# List item (lightweight, for GET /institutions/)
# ---------------------------------------------------------------------------


class InstitutionListItem(BaseModel):
    """机构列表项 — 关键字段"""

    id: str = Field(description="机构唯一 ID（通常为高校名称的拼音或缩写）")
    name: str = Field(description="机构名称（高校/院系）")
    type: str = Field(description="机构类型（university/department）")
    category: str | None = Field(default=None, description="分类（示范高校/京内高校等，仅 university）")
    priority: str | None = Field(default=None, description="优先级（P0/P1/P2/P3，仅 university）")
    scholar_count: int = Field(default=0, description="学者数量")
    student_count_total: int | None = Field(default=None, description="学生总数（仅 university）")
    mentor_count: int | None = Field(default=None, description="导师总数（仅 university）")
    parent_id: str | None = Field(default=None, description="父机构 ID（仅 department）")


class InstitutionListResponse(BaseModel):
    """Response for GET /institutions/."""

    total: int = Field(description="符合条件的总机构数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
    total_pages: int = Field(description="总页数")
    items: list[InstitutionListItem]


# ---------------------------------------------------------------------------
# Detail response (full institution record)
# ---------------------------------------------------------------------------


class InstitutionDetailResponse(BaseModel):
    """完整机构记录：基本信息 + 人员 + 合作 + 交流"""

    # 基本信息
    id: str = Field(description="机构唯一 ID")
    name: str = Field(description="机构名称")
    type: str = Field(description="机构类型（university/department）")
    org_name: str | None = Field(default=None, description="AMiner 标准化机构名（高校级别）")

    # 高校特有字段（type=university 时有值）
    category: str | None = Field(default=None, description="分类（示范高校/京内高校等）")
    priority: str | None = Field(default=None, description="优先级（P0/P1/P2/P3）")
    student_count_24: int | None = Field(default=None, description="24级学生人数")
    student_count_25: int | None = Field(default=None, description="25级学生人数")
    student_count_total: int | None = Field(default=None, description="学生总数")
    mentor_count: int | None = Field(default=None, description="导师总数")
    resident_leaders: list[str] = Field(default_factory=list, description="驻院领导及共建老师")
    degree_committee: list[str] = Field(default_factory=list, description="学位委员")
    teaching_committee: list[str] = Field(default_factory=list, description="教学委员")
    mentor_info: MentorInfo | None = Field(default=None, description="共建导师信息")
    university_leaders: list[ScholarInfo] = Field(default_factory=list, description="相关校领导")
    notable_scholars: list[ScholarInfo] = Field(default_factory=list, description="重要学者")
    key_departments: list[str] = Field(default_factory=list, description="重点院系")
    joint_labs: list[str] = Field(default_factory=list, description="联合实验室")
    training_cooperation: list[str] = Field(default_factory=list, description="培养合作")
    academic_cooperation: list[str] = Field(default_factory=list, description="学术合作")
    talent_dual_appointment: list[str] = Field(default_factory=list, description="人才双聘")
    recruitment_events: list[str] = Field(default_factory=list, description="招生宣讲")
    visit_exchanges: list[str] = Field(default_factory=list, description="交流互访")
    cooperation_focus: list[str] = Field(default_factory=list, description="合作重点")

    # 院系特有字段（type=department 时有值）
    parent_id: str | None = Field(default=None, description="父机构 ID（所属高校）")
    departments: list[DepartmentInfo] = Field(default_factory=list, description="子院系列表（仅 university）")

    # 共同字段
    scholar_count: int = Field(default=0, description="学者数量")
    sources: list[DepartmentSource] = Field(default_factory=list, description="信源列表（仅 department）")

    # 元数据
    last_updated: str | None = Field(default=None, description="最后更新时间 ISO8601")


# ---------------------------------------------------------------------------
# Stats response (for GET /institutions/stats)
# ---------------------------------------------------------------------------


class InstitutionStatsResponse(BaseModel):
    total_universities: int = Field(description="总高校数")
    total_departments: int = Field(description="总院系数")
    total_scholars: int = Field(description="总学者数")
    by_category: list[dict[str, Any]] = Field(
        description="按分类统计 [{category, count}]"
    )
    by_priority: list[dict[str, Any]] = Field(
        description="按优先级统计 [{priority, count}]"
    )
    total_students: int = Field(description="学生总数")
    total_mentors: int = Field(description="导师总数")


# ---------------------------------------------------------------------------
# Write request schemas
# ---------------------------------------------------------------------------


class InstitutionCreate(BaseModel):
    """POST /institutions/ — 创建新机构记录（支持 Excel 批量导入全量字段）"""

    # ---- 必填 ----
    id: str = Field(description="机构唯一 ID（高校/院系缩写，全局唯一）")
    name: str = Field(description="机构名称")
    type: str = Field(description="机构类型：university | department")

    # ---- 院系专用 ----
    parent_id: str | None = Field(default=None, description="父高校 ID（type=department 时必填）")

    # ---- AMiner 标准化名（可选，不填则创建后自动从 AMiner 查询写入）----
    org_name: str | None = Field(default=None, description="AMiner 标准化机构英文名，留空则自动从 AMiner 获取")

    # ---- 高校分类与优先级 ----
    category: str | None = Field(default=None, description="分类（示范高校/京内高校/京外C9/京外重点等，仅 university）")
    priority: str | None = Field(default=None, description="优先级（P0/P1/P2/P3，仅 university）")

    # ---- 高校学生与导师数 ----
    student_count_24: int | None = Field(default=None, description="24 级学生人数")
    student_count_25: int | None = Field(default=None, description="25 级学生人数")
    mentor_count: int | None = Field(default=None, description="共建导师总数")

    # ---- 高校人员信息（逗号或列表均可） ----
    resident_leaders: list[str] | None = Field(default=None, description="驻院领导及共建老师列表")
    degree_committee: list[str] | None = Field(default=None, description="学位委员列表")
    teaching_committee: list[str] | None = Field(default=None, description="教学委员列表")
    university_leaders: list[str] | None = Field(default=None, description="相关校领导列表")
    notable_scholars: list[str] | None = Field(default=None, description="重要学者列表")

    # ---- 高校合作信息 ----
    key_departments: list[str] | None = Field(default=None, description="重点院系列表")
    joint_labs: list[str] | None = Field(default=None, description="联合实验室列表")
    training_cooperation: list[str] | None = Field(default=None, description="培养合作列表")
    academic_cooperation: list[str] | None = Field(default=None, description="学术合作列表")
    talent_dual_appointment: list[str] | None = Field(default=None, description="人才双聘列表")
    recruitment_events: list[str] | None = Field(default=None, description="招生宣讲列表")
    visit_exchanges: list[str] | None = Field(default=None, description="交流互访列表")
    cooperation_focus: list[str] | None = Field(default=None, description="合作重点列表")


class InstitutionUpdate(BaseModel):
    """PATCH /institutions/{id} — 更新机构信息（所有字段可选）"""

    name: str | None = Field(default=None, description="机构名称")
    category: str | None = Field(default=None, description="分类")
    priority: str | None = Field(default=None, description="优先级")
    student_count_24: int | None = Field(default=None, description="24级学生人数")
    student_count_25: int | None = Field(default=None, description="25级学生人数")
    mentor_count: int | None = Field(default=None, description="导师总数")
    resident_leaders: list[str] | None = Field(default=None, description="驻院领导及共建老师")
    degree_committee: list[str] | None = Field(default=None, description="学位委员")
    teaching_committee: list[str] | None = Field(default=None, description="教学委员")
    university_leaders: list[ScholarInfo] | None = Field(default=None, description="相关校领导")
    notable_scholars: list[ScholarInfo] | None = Field(default=None, description="重要学者")
    key_departments: list[str] | None = Field(default=None, description="重点院系")
    joint_labs: list[str] | None = Field(default=None, description="联合实验室")
    training_cooperation: list[str] | None = Field(default=None, description="培养合作")
    academic_cooperation: list[str] | None = Field(default=None, description="学术合作")
    talent_dual_appointment: list[str] | None = Field(default=None, description="人才双聘")
    recruitment_events: list[str] | None = Field(default=None, description="招生宣讲")
    visit_exchanges: list[str] | None = Field(default=None, description="交流互访")
    cooperation_focus: list[str] | None = Field(default=None, description="合作重点")


# ---------------------------------------------------------------------------
# Scholar Institutions API schemas (for /api/v1/institutions/scholars/)
# ---------------------------------------------------------------------------


class ScholarDepartment(BaseModel):
    """院系信息（学者维度）"""

    name: str = Field(description="院系名称")
    scholar_count: int = Field(default=0, description="学者数量")
    org_name: str | None = Field(default=None, description="AMiner 标准化机构名（院系级别）")


class ScholarUniversity(BaseModel):
    """高校详情（学者维度）"""

    id: str = Field(description="高校 ID")
    name: str = Field(description="高校名称")
    scholar_count: int = Field(default=0, description="学者总数")
    departments: list[ScholarDepartment] = Field(default_factory=list, description="院系列表")
    org_name: str | None = Field(default=None, description="AMiner 标准化机构名（高校级别）")


class ScholarInstitutionsListResponse(BaseModel):
    """GET /institutions/scholars/ 响应"""

    total: int = Field(description="符合条件的总高校数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
    total_pages: int = Field(description="总页数")
    items: list[ScholarUniversity] = Field(description="高校列表")


class ScholarInstitutionsStatsResponse(BaseModel):
    """GET /institutions/scholars/stats 响应"""

    total_universities: int = Field(description="总高校数")
    total_departments: int = Field(description="总院系数")
    total_scholars: int = Field(description="总学者数")
