"""Pydantic schemas for the Institution API (/api/v1/institutions/)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------


class ScholarInfo(BaseModel):
    """学者信息（校领导/重要学者）"""

    name: str = Field(description="姓名")
    scholar_id: str | None = Field(default=None, description="学者 ID（scholars.id）")
    title: str | None = Field(default=None, description="头衔（院士/校长/书记等）")
    department: str | None = Field(default=None, description="所属院系")
    research_area: str | None = Field(default=None, description="研究方向")


class DepartmentInfo(BaseModel):
    """院系信息"""

    id: str = Field(description="院系 ID")
    name: str = Field(description="院系名称")
    scholar_count: int = Field(default=0, description="学者数量")
    org_name: str | None = Field(default=None, description="AMiner 标准化机构名（院系级别）")
    parent_id: str | None = Field(default=None, description="父机构 ID")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="院系关联信源列表")


# ---------------------------------------------------------------------------
# List item (lightweight, for GET /institutions/)
# ---------------------------------------------------------------------------


class InstitutionListItem(BaseModel):
    """机构列表项 — 关键字段"""

    id: str = Field(description="机构唯一 ID（通常为高校名称的拼音或缩写）")
    name: str = Field(description="机构名称（高校/院系）")

    # 分类字段
    entity_type: str | None = Field(default=None, description="实体类型（organization | department）")
    region: str | None = Field(default=None, description="地域（国内 | 国际）")
    org_type: str | None = Field(default=None, description="机构类型（高校 | 企业 | 研究机构 | 行业学会 | 其他）")
    classification: str | None = Field(default=None, description="顶层分类（共建高校 | 兄弟院校 | 海外高校 | 其他高校）")
    sub_classification: str | None = Field(default=None, description="二级分类")

    # 旧字段兼容
    type: str | None = Field(default=None, description="[兼容] 旧版类型字段")
    group: str | None = Field(default=None, description="[兼容] 旧版分组字段")
    category: str | None = Field(default=None, description="[兼容] 旧版分类字段")

    priority: str | None = Field(default=None, description="优先级（P0/P1/P2/P3，仅高校）")
    scholar_count: int = Field(default=0, description="学者数量")
    student_count_total: int | None = Field(default=None, description="学生总数（仅高校）")
    mentor_count: int | None = Field(default=None, description="导师总数（仅高校）")
    parent_id: str | None = Field(default=None, description="父机构 ID（仅 department）")
    avatar: str | None = Field(default=None, description="机构校徽图片链接")
    org_name: str | None = Field(default=None, description="AMiner 标准化机构名")


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
    org_name: str | None = Field(default=None, description="AMiner 标准化机构名（高校级别）")
    avatar: str | None = Field(default=None, description="机构校徽图片链接")

    # 分类字段
    entity_type: str | None = Field(default=None, description="实体类型（organization | department）")
    region: str | None = Field(default=None, description="地域（国内 | 国际）")
    org_type: str | None = Field(default=None, description="机构类型（高校 | 企业 | 研究机构 | 行业学会 | 其他）")
    classification: str | None = Field(default=None, description="顶层分类（共建高校 | 兄弟院校 | 海外高校 | 其他高校）")
    sub_classification: str | None = Field(default=None, description="二级分类")

    # 旧字段兼容
    type: str | None = Field(default=None, description="[兼容] 旧版类型字段")
    group: str | None = Field(default=None, description="[兼容] 旧版分组字段")
    category: str | None = Field(default=None, description="[兼容] 旧版分类字段")

    # 高校特有字段
    priority: str | None = Field(default=None, description="优先级（P0/P1/P2/P3）")
    student_count_24: int | None = Field(default=None, description="24级学生人数")
    student_count_25: int | None = Field(default=None, description="25级学生人数")
    student_counts_by_year: dict[str, int] = Field(
        default_factory=dict,
        description="按入学年级统计（键为四位年份，如 2026）",
    )
    student_count_total: int | None = Field(default=None, description="学生总数")
    mentor_count: int | None = Field(default=None, description="导师总数")
    resident_leaders: list[str] = Field(default_factory=list, description="驻院领导及共建老师")
    degree_committee: list[str] = Field(default_factory=list, description="学位委员")
    teaching_committee: list[str] = Field(default_factory=list, description="教学委员")
    university_leaders: list[ScholarInfo] = Field(default_factory=list, description="相关校领导")
    notable_scholars: list[ScholarInfo] = Field(default_factory=list, description="重要学者")
    key_departments: list[str] = Field(default_factory=list, description="重点院系列表")
    joint_labs: list[str] = Field(default_factory=list, description="联合实验室列表")
    training_cooperation: list[str] = Field(default_factory=list, description="培养合作列表")
    academic_cooperation: list[str] = Field(default_factory=list, description="学术合作列表")
    talent_dual_appointment: list[str] = Field(default_factory=list, description="人才双聘列表")
    recruitment_events: list[str] = Field(default_factory=list, description="招生宣讲列表")
    visit_exchanges: list[str] = Field(default_factory=list, description="交流互访列表")
    cooperation_focus: list[str] = Field(default_factory=list, description="合作重点列表")
    custom_fields: dict[str, str] = Field(default_factory=dict, description="用户自定义字段")

    # 院系特有字段
    parent_id: str | None = Field(default=None, description="父机构 ID（所属高校）")
    departments: list[DepartmentInfo] = Field(default_factory=list, description="子院系列表（仅高校）")

    # 共同字段
    scholar_count: int = Field(default=0, description="学者数量")

    # 元数据
    last_updated: str | None = Field(default=None, description="最后更新时间 ISO8601")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="机构关联信源列表")


# ---------------------------------------------------------------------------
# Stats response (for GET /institutions/stats)
# ---------------------------------------------------------------------------


class InstitutionStatsResponse(BaseModel):
    total_universities: int = Field(description="总高校数")
    total_departments: int = Field(description="总院系数")
    total_scholars: int = Field(description="总学者数")
    by_category: list[dict[str, Any]] = Field(
        description="按分类统计 [{classification, count}]"
    )
    by_priority: list[dict[str, Any]] = Field(
        description="按优先级统计 [{priority, count}]"
    )
    total_students: int = Field(description="学生总数")
    total_mentors: int = Field(description="导师总数")


# ---------------------------------------------------------------------------
# Write request schemas
# ---------------------------------------------------------------------------


class DepartmentCreateInput(BaseModel):
    """院系创建输入（用于批量创建或嵌套创建）"""

    name: str = Field(description="院系名称")
    id: str | None = Field(default=None, description="院系唯一 ID（全局唯一）。不提供则自动生成")
    org_name: str | None = Field(default=None, description="AMiner 标准化机构名（院系级别）")


class DepartmentUpdateInput(BaseModel):
    """院系更新输入（用于机构 PATCH 中的 departments 字段）"""

    id: str | None = Field(default=None, description="院系 ID（不传则自动生成）")
    name: str = Field(description="院系名称")
    org_name: str | None = Field(default=None, description="AMiner 标准化机构名（院系级别）")


class InstitutionCreate(BaseModel):
    """POST /institutions/ — 创建新机构记录

    场景 1: 创建高校（organization）
        - 必填：name, entity_type='organization', org_type='高校'
        - 可选：id（不提供则自动生成）, region, classification, priority 等

    场景 2: 创建院系（高校已存在）
        - 必填：name, entity_type='department', parent_id

    场景 3: 创建高校 + 院系（一次性创建）
        - 必填：name, entity_type='organization'
        - 可选：departments 列表
    """

    # ---- 必填 ----
    name: str = Field(description="机构名称")
    entity_type: str | None = Field(default=None, description="实体类型：organization | department")

    # ---- 兼容旧字段 ----
    type: str | None = Field(default=None, description="[已废弃] 旧版类型字段，使用 entity_type 代替")

    # ---- 可选：自动生成或用户提供 ----
    id: str | None = Field(default=None, description="机构唯一 ID。不提供则从 name 自动生成")

    @model_validator(mode="after")
    def _resolve_entity_type(self) -> "InstitutionCreate":
        """从旧版 type 字段推导 entity_type（向后兼容）."""
        if not self.entity_type and self.type:
            _type_map = {
                "university": "organization",
                "department": "department",
                "research_institute": "organization",
                "academic_society": "organization",
            }
            self.entity_type = _type_map.get(self.type, "organization")
        if not self.entity_type:
            self.entity_type = "organization"
        return self

    # ---- 分类字段 ----
    region: str | None = Field(default=None, description="地域（国内 | 国际）")
    org_type: str | None = Field(default=None, description="机构类型（高校 | 企业 | 研究机构 | 行业学会 | 其他）")
    classification: str | None = Field(default=None, description="顶层分类（共建高校 | 兄弟院校 | 海外高校 | 其他高校）")
    sub_classification: str | None = Field(default=None, description="二级分类")

    # ---- 院系专用 ----
    parent_id: str | None = Field(default=None, description="父高校 ID（entity_type=department 时必填）")

    # ---- 高校 + 院系批量创建 ----
    departments: list[DepartmentCreateInput] | None = Field(
        default=None,
        description="院系列表（entity_type=organization 时可选，支持一次性创建高校+院系）"
    )

    # ---- AMiner 标准化名 ----
    org_name: str | None = Field(default=None, description="AMiner 标准化机构英文名，留空则自动从 AMiner 获取")

    # ---- 高校优先级 ----
    priority: str | None = Field(default=None, description="优先级（P0/P1/P2/P3，仅高校）")

    # ---- 高校学生与导师数 ----
    student_count_24: int | None = Field(default=None, description="24 级学生人数")
    student_count_25: int | None = Field(default=None, description="25 级学生人数")
    mentor_count: int | None = Field(default=None, description="共建导师总数")

    # ---- 高校人员信息 ----
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
    custom_fields: dict[str, str] | None = Field(
        default=None, description="用户自定义字段（KV 键值对）",
    )


class InstitutionUpdate(BaseModel):
    """PATCH /institutions/{id} — 更新机构信息（所有字段可选）"""

    name: str | None = Field(default=None, description="机构名称")
    org_name: str | None = Field(default=None, description="AMiner 标准化机构名")
    avatar: str | None = Field(default=None, description="机构校徽图片链接")
    entity_type: str | None = Field(default=None, description="实体类型（organization | department）")
    parent_id: str | None = Field(default=None, description="父机构 ID（entity_type=department 时可用）")
    region: str | None = Field(default=None, description="地域（国内 | 国际）")
    org_type: str | None = Field(default=None, description="机构类型（高校 | 企业 | 研究机构 | 行业学会 | 其他）")
    classification: str | None = Field(default=None, description="顶层分类（共建高校 | 兄弟院校 | 海外高校 | 其他高校）")
    sub_classification: str | None = Field(default=None, description="二级分类")
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
    departments: list[DepartmentUpdateInput] | None = Field(
        default=None,
        description="二级机构列表（仅一级机构可用，传入时按全量同步）",
    )
    custom_fields: dict[str, str | None] | None = Field(
        default=None, description="用户自定义字段（浅合并：值为 null 删除该 key）",
    )


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
    avatar: str | None = Field(default=None, description="机构校徽图片链接")


# ---------------------------------------------------------------------------
# Institution Tree API schemas (for /api/v1/institutions/scholars/tree)
# ---------------------------------------------------------------------------


class InstitutionTreeDepartment(BaseModel):
    """院系节点"""

    name: str = Field(description="院系名称")
    scholar_count: int = Field(default=0, description="学者数量")


class InstitutionTreeInstitution(BaseModel):
    """机构节点（高校/科研院所/学会等）"""

    id: str = Field(description="机构 ID")
    name: str = Field(description="机构名称")
    scholar_count: int = Field(default=0, description="学者数量")
    departments: list[InstitutionTreeDepartment] = Field(default_factory=list, description="院系列表")
    avatar: str | None = Field(default=None, description="机构校徽图片链接")


class InstitutionTreeCategory(BaseModel):
    """细粒度分类节点（示范性合作伙伴/京内高校/京外C9 等）"""

    category: str = Field(description="分类名称")
    scholar_count: int = Field(default=0, description="该分类学者总数")
    institutions: list[InstitutionTreeInstitution] = Field(default_factory=list, description="机构列表")


class InstitutionTreeGroup(BaseModel):
    """顶层分组节点（共建高校/兄弟院校/海外高校/其他高校/科研院所/行业学会）"""

    group: str = Field(description="分组名称")
    scholar_count: int = Field(default=0, description="该分组学者总数")
    categories: list[InstitutionTreeCategory] = Field(default_factory=list, description="分类列表")


class InstitutionTreeResponse(BaseModel):
    """GET /institutions/scholars/tree 响应 — 机构分类树"""

    total_scholar_count: int = Field(description="学者总数")
    groups: list[InstitutionTreeGroup] = Field(description="顶层分组列表")


# ---------------------------------------------------------------------------
# Institution Search API schemas (for /api/v1/institutions/search)
# ---------------------------------------------------------------------------


class InstitutionSearchResult(BaseModel):
    """机构搜索结果项"""

    id: str = Field(description="机构 ID")
    name: str = Field(description="机构名称")
    entity_type: str | None = Field(default=None, description="实体类型（organization | department）")
    region: str | None = Field(default=None, description="地域（国内 | 国际）")
    org_type: str | None = Field(default=None, description="机构类型（高校 | 企业 | 研究机构 | 其他）")
    parent_id: str | None = Field(default=None, description="父机构 ID（仅 department）")
    scholar_count: int = Field(default=0, description="学者数量")


class InstitutionSearchResponse(BaseModel):
    """GET /institutions/search 响应"""

    query: str = Field(description="搜索关键词")
    total: int = Field(description="结果总数")
    results: list[InstitutionSearchResult] = Field(description="搜索结果列表")


class InstitutionSuggestionResponse(BaseModel):
    """GET /institutions/suggest 响应"""

    university: str = Field(description="输入的大学名称")
    matched: InstitutionSearchResult | None = Field(default=None, description="最佳匹配（强匹配）")
    suggestions: list[InstitutionSearchResult] = Field(default_factory=list, description="建议列表")


# ---------------------------------------------------------------------------
# University Leadership API schemas
# ---------------------------------------------------------------------------


class UniversityLeadershipMember(BaseModel):
    """高校领导成员（爬虫结果）"""

    name: str = Field(description="姓名")
    role: str = Field(description="职务")
    profile_url: str | None = Field(default=None, description="个人主页链接")
    avatar_url: str | None = Field(default=None, description="头像链接")
    bio: str | None = Field(default=None, description="简介全文")
    intro_lines: list[str] = Field(default_factory=list, description="简介摘要段落")
    source_page_url: str | None = Field(default=None, description="来源列表页 URL")
    detail_name_text: str | None = Field(default=None, description="详情页标题文本")


class UniversityLeadershipCurrentResponse(BaseModel):
    """当前高校领导信息（按学校最新版本）"""

    source_id: str = Field(description="信源 ID")
    institution_id: str | None = Field(default=None, description="机构 ID")
    university_name: str = Field(description="高校名称")
    source_name: str | None = Field(default=None, description="信源名称")
    source_url: str | None = Field(default=None, description="信源 URL")
    dimension: str | None = Field(default=None, description="维度")
    group: str | None = Field(default=None, description="分组")
    crawled_at: datetime | None = Field(default=None, description="最近爬取时间 ISO8601")
    previous_crawled_at: datetime | None = Field(default=None, description="上次爬取时间 ISO8601")
    leader_count: int = Field(default=0, description="领导总数")
    new_leader_count: int = Field(default=0, description="相对上次新增人数")
    role_counts: dict[str, int] = Field(default_factory=dict, description="按职务统计")
    leaders: list[UniversityLeadershipMember] = Field(default_factory=list, description="领导列表")
    data_hash: str | None = Field(default=None, description="数据哈希")
    change_version: int = Field(default=1, description="版本号（变化+1）")
    last_changed_at: datetime | None = Field(default=None, description="最近变更时间 ISO8601")
    updated_at: datetime | None = Field(default=None, description="记录更新时间 ISO8601")


class UniversityLeadershipListResponse(BaseModel):
    """高校领导列表（分页）"""

    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="页码")
    page_size: int = Field(default=20, description="每页数量")
    items: list[UniversityLeadershipCurrentResponse] = Field(default_factory=list, description="列表项")


class UniversityLeadershipAllResponse(BaseModel):
    """高校领导全量数据"""

    total: int = Field(default=0, description="总数")
    items: list[UniversityLeadershipCurrentResponse] = Field(default_factory=list, description="全部高校领导数据")


class UniversityLeadershipSnapshotItem(BaseModel):
    """高校领导月度快照记录"""

    snapshot_id: int | None = Field(default=None, description="快照 ID")
    source_id: str = Field(description="信源 ID")
    institution_id: str | None = Field(default=None, description="机构 ID")
    university_name: str = Field(description="高校名称")
    source_name: str | None = Field(default=None, description="信源名称")
    source_url: str | None = Field(default=None, description="信源 URL")
    crawl_month: date | None = Field(default=None, description="快照月份（YYYY-MM-01）")
    crawled_at: datetime | None = Field(default=None, description="爬取时间 ISO8601")
    previous_crawled_at: datetime | None = Field(default=None, description="上次爬取时间 ISO8601")
    leader_count: int = Field(default=0, description="领导总数")
    new_leader_count: int = Field(default=0, description="新增人数")
    role_counts: dict[str, int] = Field(default_factory=dict, description="按职务统计")
    leaders: list[UniversityLeadershipMember] = Field(default_factory=list, description="领导列表")
    data_hash: str | None = Field(default=None, description="数据哈希")
    changed: bool = Field(default=False, description="相对上次是否变化")
    change_summary: dict[str, Any] = Field(default_factory=dict, description="变化摘要")
    updated_at: datetime | None = Field(default=None, description="记录更新时间 ISO8601")


class UniversityLeadershipHistoryResponse(BaseModel):
    """高校领导历史快照列表"""

    institution_id: str = Field(description="机构 ID")
    university_name: str = Field(description="高校名称")
    total: int = Field(default=0, description="返回条数")
    items: list[UniversityLeadershipSnapshotItem] = Field(default_factory=list, description="历史快照")


class UniversityLeadershipCrawlSourceResult(BaseModel):
    """全量抓取单信源执行结果"""

    source_id: str = Field(description="信源 ID")
    source_name: str | None = Field(default=None, description="信源名称")
    university_name: str | None = Field(default=None, description="高校名称")
    status: str = Field(description="执行状态")
    error: str | None = Field(default=None, description="错误信息")
    leaders_total: int = Field(default=0, description="抓取到的领导人数")
    changed: bool = Field(default=False, description="是否触发数据变化")
    new_leader_count: int | None = Field(default=None, description="新增领导数")
    change_version: int | None = Field(default=None, description="版本号")
    duration_seconds: float = Field(default=0.0, description="耗时（秒）")
    started_at: datetime | None = Field(default=None, description="开始时间 ISO8601")
    finished_at: datetime | None = Field(default=None, description="结束时间 ISO8601")


class UniversityLeadershipCrawlRunResponse(BaseModel):
    """全量抓取任务结果"""

    started_at: datetime | None = Field(default=None, description="任务开始时间 ISO8601")
    finished_at: datetime | None = Field(default=None, description="任务结束时间 ISO8601")
    duration_seconds: float | None = Field(default=None, description="任务耗时（秒）")
    total_sources: int = Field(default=0, description="总信源数")
    success_sources: int = Field(default=0, description="成功数")
    failed_sources: int = Field(default=0, description="失败数")
    changed_sources: int = Field(default=0, description="发生变化的信源数")
    results: list[UniversityLeadershipCrawlSourceResult] = Field(default_factory=list, description="明细")


class InstitutionScholarCandidate(BaseModel):
    """可选学者候选项（用于手工配置机构人员）"""

    scholar_id: str = Field(description="学者 ID")
    name: str = Field(description="姓名")
    university: str | None = Field(default=None, description="高校")
    department: str | None = Field(default=None, description="院系")
    position: str | None = Field(default=None, description="职称/职务")
    photo_url: str | None = Field(default=None, description="头像")
    research_areas: list[str] = Field(default_factory=list, description="研究方向")


class InstitutionScholarCandidateResponse(BaseModel):
    """机构学者候选列表响应"""

    institution_id: str = Field(description="机构 ID")
    institution_name: str = Field(description="机构名称")
    query: str = Field(description="关键词")
    total: int = Field(description="结果数")
    items: list[InstitutionScholarCandidate] = Field(default_factory=list, description="候选项列表")


class InstitutionManualPeopleUpdate(BaseModel):
    """机构手工人员配置（从 scholars 表引用）"""

    governance_scholar_ids: list[str] = Field(default_factory=list, description="负责人/治理团队学者 ID 列表")
    notable_scholar_ids: list[str] = Field(default_factory=list, description="知名学者 ID 列表（最多 10）")
    enforce_same_university: bool = Field(default=True, description="是否限制为同一高校学者")

    @field_validator("notable_scholar_ids")
    @classmethod
    def _validate_notable_limit(cls, value: list[str]) -> list[str]:
        if len(value) > 10:
            raise ValueError("notable_scholar_ids 最多 10 位")
        return value
