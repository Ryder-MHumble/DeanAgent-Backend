"""Pydantic schemas for the Institution API (/api/v1/institutions/)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------


class InstituteLeader(BaseModel):
    """驻院领导或共建老师信息"""

    name: str = Field(description="姓名")
    institute_role: str = Field(default="", description="在学院的任职")
    university_role: str = Field(default="", description="在高校的任职")


class CommitteeMember(BaseModel):
    """委员会成员信息"""

    name: str = Field(description="姓名")
    role: str = Field(default="", description="职务/职称")
    department: str = Field(default="", description="所属院系")


class JointSupervisor(BaseModel):
    """共建导师信息"""

    name: str = Field(description="姓名")
    category: str = Field(default="", description="类别（教学研究/研究等）")
    department: str = Field(default="", description="所属院系")


class UniversityLeader(BaseModel):
    """相关校领导信息"""

    name: str = Field(description="姓名")
    title: str = Field(default="", description="头衔（校长/书记/副校长等）")
    research_area: str = Field(default="", description="研究方向")


class ImportantScholar(BaseModel):
    """重要学者信息"""

    name: str = Field(description="姓名")
    title: str = Field(default="", description="学术头衔（院士等）")
    department: str = Field(default="", description="所属院系")
    research_area: str = Field(default="", description="研究方向")


class CollaborationInfo(BaseModel):
    """合作信息"""

    joint_lab: str = Field(default="", description="联合实验室")
    training: str = Field(default="", description="培养合作")
    academic: str = Field(default="", description="学术合作")
    talent_hiring: str = Field(default="", description="人才双聘")


class ExchangeRecord(BaseModel):
    """交流互访记录"""

    date: str = Field(default="", description="日期 YYYY-MM-DD")
    event: str = Field(description="事件描述")
    participants: str = Field(default="", description="参与人员")


# ---------------------------------------------------------------------------
# List item (lightweight, for GET /institutions/)
# ---------------------------------------------------------------------------


class InstitutionListItem(BaseModel):
    """机构列表项 — 关键字段"""

    id: str = Field(description="机构唯一 ID（通常为高校名称的拼音或缩写）")
    name: str = Field(description="高校名称")
    category: str = Field(default="", description="分类（示范高校/京内高校/京外C9等）")
    priority: str = Field(default="", description="优先级（P0/P1/P2/P3）")
    is_demo_school: bool = Field(default=False, description="是否示范校")
    student_count_24: int = Field(default=0, description="24级学生人数")
    student_count_25: int = Field(default=0, description="25级学生人数")
    student_count_total: int = Field(default=0, description="学生总数")
    supervisor_count: int = Field(default=0, description="导师总数")
    collaboration_focus: str = Field(default="", description="合作重点")
    key_departments: list[str] = Field(default_factory=list, description="重点院系")


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
    id: str
    name: str
    category: str
    priority: str
    is_demo_school: bool

    # 学生与导师
    student_count_24: int
    student_count_25: int
    student_count_total: int
    supervisor_count: int

    # 人员信息
    institute_leaders: list[InstituteLeader] = Field(
        default_factory=list, description="驻院领导及共建老师"
    )
    degree_committee: list[CommitteeMember] = Field(
        default_factory=list, description="学位委员"
    )
    teaching_committee: list[CommitteeMember] = Field(
        default_factory=list, description="教学委员"
    )
    joint_supervisors: list[JointSupervisor] = Field(
        default_factory=list, description="共建导师"
    )
    university_leaders: list[UniversityLeader] = Field(
        default_factory=list, description="相关校领导"
    )
    important_scholars: list[ImportantScholar] = Field(
        default_factory=list, description="重要学者"
    )

    # 院系与合作
    key_departments: list[str] = Field(default_factory=list, description="重点院系")
    collaboration: CollaborationInfo = Field(
        default_factory=CollaborationInfo, description="合作信息"
    )
    collaboration_focus: str = Field(default="", description="合作重点")

    # 交流互访
    exchange_records: list[ExchangeRecord] = Field(
        default_factory=list, description="交流互访记录"
    )

    # 元数据
    data_source: str = Field(default="", description="数据来源")
    last_updated: str = Field(default="", description="最后更新时间 ISO8601")
    notes: str = Field(default="", description="备注")


# ---------------------------------------------------------------------------
# Stats response (for GET /institutions/stats)
# ---------------------------------------------------------------------------


class InstitutionStatsResponse(BaseModel):
    total: int = Field(description="总机构数")
    demo_schools: int = Field(description="示范校数量")
    by_category: list[dict[str, Any]] = Field(
        description="按分类统计 [{category, count}]"
    )
    by_priority: list[dict[str, Any]] = Field(
        description="按优先级统计 [{priority, count}]"
    )
    total_students: int = Field(description="学生总数")
    total_supervisors: int = Field(description="导师总数")
    by_collaboration_focus: list[dict[str, Any]] = Field(
        description="按合作重点统计 [{focus, count}]"
    )


# ---------------------------------------------------------------------------
# Write request schemas
# ---------------------------------------------------------------------------


class InstitutionCreate(BaseModel):
    """POST /institutions/ — 创建新机构记录"""

    id: str = Field(description="机构唯一 ID")
    name: str = Field(description="高校名称")
    category: str = Field(default="", description="分类")
    priority: str = Field(default="", description="优先级")
    is_demo_school: bool = Field(default=False, description="是否示范校")
    student_count_24: int = Field(default=0, description="24级学生人数")
    student_count_25: int = Field(default=0, description="25级学生人数")
    student_count_total: int = Field(default=0, description="学生总数")
    supervisor_count: int = Field(default=0, description="导师总数")
    collaboration_focus: str = Field(default="", description="合作重点")
    notes: str = Field(default="", description="备注")


class InstitutionUpdate(BaseModel):
    """PATCH /institutions/{id} — 更新机构信息（所有字段可选）"""

    name: str | None = Field(default=None, description="高校名称")
    category: str | None = Field(default=None, description="分类")
    priority: str | None = Field(default=None, description="优先级")
    is_demo_school: bool | None = Field(default=None, description="是否示范校")
    student_count_24: int | None = Field(default=None, description="24级学生人数")
    student_count_25: int | None = Field(default=None, description="25级学生人数")
    student_count_total: int | None = Field(default=None, description="学生总数")
    supervisor_count: int | None = Field(default=None, description="导师总数")
    institute_leaders: list[InstituteLeader] | None = Field(
        default=None, description="驻院领导及共建老师"
    )
    degree_committee: list[CommitteeMember] | None = Field(
        default=None, description="学位委员"
    )
    teaching_committee: list[CommitteeMember] | None = Field(
        default=None, description="教学委员"
    )
    joint_supervisors: list[JointSupervisor] | None = Field(
        default=None, description="共建导师"
    )
    university_leaders: list[UniversityLeader] | None = Field(
        default=None, description="相关校领导"
    )
    important_scholars: list[ImportantScholar] | None = Field(
        default=None, description="重要学者"
    )
    key_departments: list[str] | None = Field(default=None, description="重点院系")
    collaboration: CollaborationInfo | None = Field(default=None, description="合作信息")
    collaboration_focus: str | None = Field(default=None, description="合作重点")
    exchange_records: list[ExchangeRecord] | None = Field(
        default=None, description="交流互访记录"
    )
    notes: str | None = Field(default=None, description="备注")
    updated_by: str = Field(default="user", description="更新人")


class ExchangeRecordCreate(BaseModel):
    """POST /institutions/{id}/exchanges — 添加交流互访记录"""

    date: str = Field(description="日期 YYYY-MM-DD")
    event: str = Field(description="事件描述")
    participants: str = Field(default="", description="参与人员")
    added_by: str = Field(default="user", description="录入人")
