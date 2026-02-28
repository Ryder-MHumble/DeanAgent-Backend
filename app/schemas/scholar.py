"""ScholarRecord — unified schema for academic scholar/faculty data.

Field design principles:
- Missing data → "" (str) / [] (list) / -1 (int metric, -1 = unknown) — never null
- All field names use snake_case for direct database column mapping
- `extra` in CrawledItem stores model_dump() of this schema
- On DB migration: SELECT from university_faculty dimension's latest.json,
  extract extra field → insert into scholars table directly

Data source labels (in field docstrings):
  [爬虫]    Populated by FacultyCrawler automatically
  [富化]    Populated by LLM enrichment or external API (Google Scholar/DBLP)
  [用户]    Manually maintained by internal staff — never overwritten by crawler

Data completeness score (data_completeness: 0–100) measures CRAWL quality only,
not user-maintained fields.

Sections
--------
基本信息      name, name_en, gender, photo_url
机构归属      university, department, secondary_departments
职称荣誉      position, academic_titles, is_academician
研究方向      research_areas, keywords, bio, bio_en
联系方式      email, phone, office
主页链接      profile_url, lab_url, google_scholar_url, dblp_url, orcid
教育经历      phd_institution, phd_year, education
学术指标      publications_count, h_index, citations_count, metrics_updated_at
与两院关系    is_advisor_committee, is_adjunct_supervisor, supervised_students,
              joint_research_projects, joint_management_roles,
              academic_exchange_records, is_potential_recruit,
              institute_relation_notes, relation_updated_by, relation_updated_at
动态更新      recent_updates (list[DynamicUpdate])
元信息        source_id, source_url, crawled_at, first_seen_at, last_seen_at,
              is_active, data_completeness
"""
from __future__ import annotations

import re as _re

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class EducationRecord(BaseModel):
    """Single education entry (degree, institution, year). [富化]"""

    degree: str = ""         # 学历: "博士" | "硕士" | "学士" | "博士后"
    institution: str = ""    # 毕业/研修院校
    year: str = ""           # 毕业年份（字符串支持 "2003–2007" 区间）
    major: str = ""          # 专业/研究方向


class DynamicUpdate(BaseModel):
    """A single time-stamped dynamic event for a scholar.

    Sources:
    - Crawled automatically from the scholar's personal page, news sites, etc.
    - Manually added by internal staff (added_by starts with "user:")
    """

    update_type: str = ""
    """事件类型:
    'major_project'   重大项目立项（国家级/省部级重点项目）
    'talent_title'    人才称号（新获杰青/长江/优青/院士等称号）
    'position_change' 任职履新（新职位/晋升/退休/离职）
    'award'           获奖（科技奖/学术奖等具体奖项）
    'publication'     重要论文/著作发表
    'other'           其他重要动态
    """

    title: str = ""
    """更新标题/摘要，如 '获批国家自然科学基金重大项目'"""

    content: str = ""
    """详细内容描述"""

    source_url: str = ""
    """来源 URL（爬虫数据时填写）"""

    published_at: str = ""
    """事件发生/发布时间 ISO8601"""

    crawled_at: str = ""
    """爬取/录入时间 ISO8601（自动填写）"""

    added_by: str = "crawler"
    """数据来源: 'crawler' | 'user:{username}'（区分自动爬取与人工录入）"""


# ---------------------------------------------------------------------------
# Main schema
# ---------------------------------------------------------------------------


class ScholarRecord(BaseModel):
    """Unified schema for a university faculty / researcher record.

    Stored as CrawledItem.extra (model_dump()) by FacultyCrawler.
    Designed for forward-compatibility with a relational scholars table.

    Two sections require special handling:
    - 与两院关系: user-editable fields ([用户]), never overwritten by crawler
    - 动态更新: primarily crawled but also user-addable via API
    """

    # ===== 基本信息 [爬虫] =====
    name: str = ""
    """中文姓名（必填，去重 title 字段）"""

    name_en: str = ""
    """英文姓名，如 'Ya-Qin Zhang' [富化]"""

    gender: str = ""
    """性别: 'male' | 'female' | ''（未知）[富化]"""

    photo_url: str = ""
    """照片绝对 URL [爬虫]"""

    # ===== 机构归属 [爬虫] =====
    university: str = ""
    """所属大学全称，如 '清华大学'"""

    department: str = ""
    """所属院系全称，如 '计算机科学与技术系'"""

    secondary_departments: list[str] = Field(default_factory=list)
    """兼职/双聘院系列表 [富化]，如 ['人工智能研究院', '交叉信息研究院']"""

    # ===== 职称荣誉 [爬虫/富化] =====
    position: str = ""
    """职称，如 '教授' | '副教授' | '助理教授' | '研究员' | '副研究员'"""

    academic_titles: list[str] = Field(default_factory=list)
    """学术头衔列表 [富化]，如 ['长江学者', '杰青', '优青', '国家特聘专家', '院士']"""

    is_academician: bool = False
    """是否为中科院/工程院院士 [富化]"""

    # ===== 研究方向 [爬虫/富化] =====
    research_areas: list[str] = Field(default_factory=list)
    """研究方向列表，如 ['机器学习', '计算机视觉', '自然语言处理']"""

    keywords: list[str] = Field(default_factory=list)
    """细粒度关键词，用于检索与标签 [富化]"""

    bio: str = ""
    """中文个人简介/研究简介（完整纯文本）[爬虫]"""

    bio_en: str = ""
    """英文个人简介 [富化]"""

    # ===== 联系方式 [爬虫] =====
    email: str = ""
    """主联系邮箱，如 'xxx@tsinghua.edu.cn'"""

    phone: str = ""
    """联系电话"""

    office: str = ""
    """办公室地址，如 '东主楼 10-103'"""

    # ===== 主页与链接 [爬虫/富化] =====
    profile_url: str = ""
    """个人主页 URL，作为 CrawledItem.url 的去重 key [爬虫]"""

    lab_url: str = ""
    """实验室/课题组主页 URL [爬虫]"""

    google_scholar_url: str = ""
    """Google Scholar 主页 URL [富化]"""

    dblp_url: str = ""
    """DBLP 作者主页 URL [富化]"""

    orcid: str = ""
    """ORCID ID，如 '0000-0001-2345-6789' [富化]"""

    # ===== 教育经历 [富化] =====
    phd_institution: str = ""
    """博士毕业院校（快速检索冗余字段）"""

    phd_year: str = ""
    """博士毕业年份，如 '2005'"""

    education: list[EducationRecord] = Field(default_factory=list)
    """完整教育经历（学士/硕士/博士/博后），由详情页解析或 LLM 富化填充"""

    # ===== 学术指标 [富化，-1 表示未获取] =====
    publications_count: int = -1
    """发表论文总数（来源: Google Scholar / DBLP）"""

    h_index: int = -1
    """H 指数"""

    citations_count: int = -1
    """总被引次数"""

    metrics_updated_at: str = ""
    """学术指标最后更新时间 ISO8601"""

    # ===== 与两院关系 [用户] =====
    # 两院 = 中关村人工智能研究院（BIGAI）+ 北京中关村学院（ZGC Academy）
    # 所有字段由内部工作人员手动维护，爬虫绝不覆盖这些字段
    # -------------------------------------------------------------------------
    is_advisor_committee: bool = False
    """顾问委员（顾问委员会成员）[用户 - 综办/培养部/科研部]"""

    is_adjunct_supervisor: bool = False
    """兼职导师（与两院签订兼职导师协议）[用户 - 人力部]"""

    supervised_students: list[str] = Field(default_factory=list)
    """指导学生列表（学生姓名或 ID）[用户 - 培养部]"""

    joint_research_projects: list[str] = Field(default_factory=list)
    """与两院联合承担的科研项目名称列表 [用户 - 科研部]"""

    joint_management_roles: list[str] = Field(default_factory=list)
    """在两院担任的联合管理职务，如 '教学委员会委员' [用户 - 学工部]"""

    academic_exchange_records: list[str] = Field(default_factory=list)
    """学术交流活动记录（XAI 讲坛/联合研讨会/专题报告等）[用户 - 活动数据]"""

    is_potential_recruit: bool = False
    """潜在引进对象（通过学术顶会/青年论坛等活动识别）[用户 - 活动数据]"""

    institute_relation_notes: str = ""
    """与两院关系补充备注（自由文本）[用户]"""

    relation_updated_by: str = ""
    """两院关系数据最后更新人（内部用户名/姓名）[用户]"""

    relation_updated_at: str = ""
    """两院关系数据最后更新时间 ISO8601 [用户]"""

    # ===== 动态更新 [爬虫+用户] =====
    # 爬虫自动追加，内部人员也可通过 API 手动录入
    # 追加式写入，不覆盖历史记录
    # -------------------------------------------------------------------------
    recent_updates: list[DynamicUpdate] = Field(default_factory=list)
    """近期动态更新列表（重大项目立项/人才称号/任职履新/获奖/论文等）"""

    # ===== 元信息 [爬虫] =====
    source_id: str = ""
    """来源信源 ID，如 'tsinghua_cs_faculty'"""

    source_url: str = ""
    """爬取来源列表页 URL"""

    crawled_at: str = ""
    """本次爬取时间 ISO8601"""

    first_seen_at: str = ""
    """首次发现时间 ISO8601（首次爬到时写入，后续不覆盖）"""

    last_seen_at: str = ""
    """最后一次在目标页面确认在职的时间 ISO8601"""

    is_active: bool = True
    """是否在职（True = 本次爬取中存在；False = 历史存在但当前未见）"""

    data_completeness: int = 0
    """爬虫数据完整度 0–100（仅评估可爬取字段，不含用户维护字段）"""


# ---------------------------------------------------------------------------
# Helper: compute data completeness score (crawled fields only)
# ---------------------------------------------------------------------------

_COMPLETENESS_WEIGHTS: list[tuple[str, int]] = [
    ("name", 20),
    ("bio", 15),
    ("research_areas", 15),
    ("position", 10),
    ("email", 10),
    ("_real_profile", 10),  # profile_url without a synthetic #hash fragment
    ("photo_url", 5),
    ("phd_institution", 5),
    ("_ext_link", 5),       # lab_url or google_scholar_url
    ("keywords", 5),
]


def compute_scholar_completeness(r: ScholarRecord) -> int:
    """Return crawl data completeness score 0–100 for a ScholarRecord.

    Only evaluates automatically-populated fields ([爬虫] / [富化]).
    User-maintained 与两院关系 fields are intentionally excluded.

    Typical scores:
    - List-page only (name + photo): ~25
    - With bio + position:           ~50–60
    - With email + research_areas:   ~70–80
    - Fully enriched:                100
    """
    score = 0
    for key, weight in _COMPLETENESS_WEIGHTS:
        if key == "_real_profile":
            if r.profile_url and "#" not in r.profile_url:
                score += weight
        elif key == "_ext_link":
            if r.lab_url or r.google_scholar_url:
                score += weight
        else:
            val = getattr(r, key, None)
            if val:
                score += weight
    return min(score, 100)


# ---------------------------------------------------------------------------
# Helper: parse research areas string → list
# ---------------------------------------------------------------------------

_RA_SPLITTER = _re.compile(r"[；;、，,/\\|\n\r]+")


def parse_research_areas(raw: str) -> list[str]:
    """Split a raw research areas string into a deduplicated list.

    Handles common Chinese and ASCII delimiters.
    Example: '机器学习；计算机视觉、NLP' → ['机器学习', '计算机视觉', 'NLP']
    """
    if not raw:
        return []
    parts = _RA_SPLITTER.split(raw)
    seen: set[str] = set()
    result: list[str] = []
    for p in parts:
        p = p.strip()
        if p and p not in seen:
            seen.add(p)
            result.append(p)
    return result
