"""Institution service — 统一的机构（高校+院系）CRUD 操作."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.institution import (
    DepartmentInfo,
    DepartmentSource,
    InstitutionDetailResponse,
    InstitutionListItem,
    InstitutionListResponse,
    InstitutionStatsResponse,
    MentorInfo,
    ScholarInfo,
)

INSTITUTIONS_FILE = Path("data/scholars/institutions.json")

# ---------------------------------------------------------------------------
# 分类体系：category → group 映射
# ---------------------------------------------------------------------------

# category（细粒度分类） → group（顶层分组）
_CATEGORY_TO_GROUP: dict[str, str] = {
    # 共建高校 ---------------------------------------------------------------
    "示范性合作伙伴": "共建高校",
    "京内高校": "共建高校",
    "京外C9": "共建高校",
    "综合强校": "共建高校",
    "工科强校": "共建高校",
    "特色高校": "共建高校",
    # 兄弟院校 ---------------------------------------------------------------
    "兄弟院校": "兄弟院校",
    # 海外高校 ---------------------------------------------------------------
    "香港高校": "海外高校",
    "亚太高校": "海外高校",
    "欧美高校": "海外高校",
    "其他地区高校": "海外高校",
    # 其他高校 ---------------------------------------------------------------
    "特色专科学校": "其他高校",
    "北京市属高校": "其他高校",
    "地方重点高校": "其他高校",
    "其他高校": "其他高校",
    # 科研院所 ---------------------------------------------------------------
    "科研院所-同行业": "科研院所",
    "科研院所-交叉学科": "科研院所",
    "科研院所-国家实验室": "科研院所",
    # 行业学会 ---------------------------------------------------------------
    "行业学会": "行业学会",
}

# 顶层分组显示顺序（数字越小越靠前）
_GROUP_ORDER: dict[str, int] = {
    "共建高校": 0,
    "兄弟院校": 1,
    "海外高校": 2,
    "其他高校": 3,
    "科研院所": 4,
    "行业学会": 5,
}

# 顶层聚合分组 → 子分组映射（前端侧边栏使用）
# 例如点击「高校」时，需要匹配其下所有子分组
_PARENT_GROUP_MAP: dict[str, list[str]] = {
    "高校": ["共建高校", "兄弟院校", "海外高校", "其他高校"],
}

# category 内部排序：同一 group 内的 category 显示顺序
_CATEGORY_ORDER: dict[str, int] = {
    # 共建高校
    "示范性合作伙伴": 0,
    "京内高校": 1,
    "京外C9": 2,
    "综合强校": 3,
    "工科强校": 4,
    "特色高校": 5,
    # 海外高校
    "香港高校": 0,
    "亚太高校": 1,
    "欧美高校": 2,
    "其他地区高校": 3,
    # 其他高校
    "特色专科学校": 0,
    "北京市属高校": 1,
    "地方重点高校": 2,
    "其他高校": 3,
    # 科研院所
    "科研院所-同行业": 0,
    "科研院所-交叉学科": 1,
    "科研院所-国家实验室": 2,
}

# P0 机构内部固定排序（ID → order）：清华 > 北大 > 其他
_INSTITUTION_PRESTIGE_ORDER: dict[str, int] = {
    # 示范性合作伙伴
    "tsinghua": 0,
    "pku": 1,
    # 京外C9（复交浙南科在前）
    "fudan": 10,
    "sjtu": 11,
    "zju": 12,
    "nju": 13,
    "ustc": 14,
    "hit": 15,
    "xjtu": 16,
    # 京内高校
    "cas": 20,
    "buaa": 21,
    "bit": 22,
    "bupt": 23,
    "bnu": 24,
    "ruc": 25,
    # 海外顶尖
    "nus": 30,
    "ntu_sg": 31,
    "hku": 32,
    "cuhk": 33,
    "hkust": 34,
}


def _derive_group(category: str | None) -> str | None:
    """从 category 派生顶层分组名称."""
    if not category:
        return None
    return _CATEGORY_TO_GROUP.get(category)


def _match_group(derived_group: str | None, group_filter: str) -> bool:
    """判断机构的派生分组是否匹配 group 筛选条件.

    支持：
    - 精确匹配子分组（如 group_filter='共建高校'）
    - 聚合匹配顶层分组（如 group_filter='高校' 匹配 共建高校/兄弟院校/海外高校/其他高校）
    """
    if not derived_group:
        return False
    # 精确匹配
    if derived_group == group_filter:
        return True
    # 聚合匹配（如 高校 → [共建高校, 兄弟院校, 海外高校, 其他高校]）
    sub_groups = _PARENT_GROUP_MAP.get(group_filter)
    if sub_groups and derived_group in sub_groups:
        return True
    return False


def _normalize_priority(raw) -> int:
    """将 priority 归一化为整数（DB 存整数 0-3，或字符串 P0-P3）."""
    if raw is None:
        return 99
    if isinstance(raw, int):
        return raw
    s = str(raw).strip().upper()
    _map = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return _map.get(s, 99)


def _institution_sort_key(inst: dict) -> tuple:
    """生成机构排序 key：分组顺序 → 优先级 → category 顺序 → 声望顺序 → 名称."""
    cat = inst.get("category") or ""
    group = _derive_group(cat) or "zzz"
    return (
        0 if inst.get("type") != "department" else 1,  # 高校先于院系
        _GROUP_ORDER.get(group, 99),
        _normalize_priority(inst.get("priority")),
        _CATEGORY_ORDER.get(cat, 99),
        _INSTITUTION_PRESTIGE_ORDER.get(inst.get("id", ""), 999),
        inst.get("name", ""),
    )


class InstitutionAlreadyExistsError(ValueError):
    """Raised when trying to create an institution that already exists."""


def _get_client():
    from app.db.client import get_client  # noqa: PLC0415
    return get_client()


def _load_institutions() -> dict[str, Any]:
    """Load institutions data from JSON file."""
    if not INSTITUTIONS_FILE.exists():
        return {"last_updated": "", "universities": []}

    with open(INSTITUTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_institutions(data: dict[str, Any]) -> None:
    """Save institutions data to JSON file."""
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(INSTITUTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _flatten_institutions(universities: list[dict]) -> list[dict]:
    """将高校和院系扁平化为统一的机构列表.

    Returns:
        [
            {id, name, type='university', category, priority, scholar_count, ...},
            {id, name, type='department', parent_id, scholar_count, ...},
            ...
        ]
    """
    result = []

    for univ in universities:
        # 高校本身（数据直接存储在 univ 对象中，不在 details 字段）
        result.append({
            "id": univ["id"],
            "name": univ["name"],
            "type": "university",
            "category": univ.get("category"),
            "priority": univ.get("priority"),
            "scholar_count": univ.get("scholar_count", 0),
            "student_count_total": univ.get("student_count_total"),
            "mentor_count": univ.get("mentor_count"),
            "parent_id": None,
        })

        # 院系
        for dept in univ.get("departments", []):
            result.append({
                "id": dept["id"],
                "name": dept["name"],
                "type": "department",
                "category": None,
                "priority": None,
                "scholar_count": dept.get("scholar_count", 0),
                "student_count_total": None,
                "mentor_count": None,
                "parent_id": univ["id"],
            })

    return result


async def get_institution_list(
    type_filter: str | None = None,  # 'university' | 'department' | 'research_institute' | 'academic_society'
    group: str | None = None,        # 顶层分组：共建高校/兄弟院校/海外高校/其他高校/科研院所/行业学会
    category: str | None = None,
    priority: str | None = None,
    parent_id: str | None = None,  # 筛选某高校下的院系
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    custom_field_key: str | None = None,
    custom_field_value: str | None = None,
) -> InstitutionListResponse:
    """获取机构列表（高校+院系统一查询）."""
    # Try DB first
    try:
        client = _get_client()
        q = client.table("institutions").select(
            "id,name,type,category,priority,scholar_count,student_count_total,mentor_count,parent_id,custom_fields"
        )
        if type_filter:
            q = q.eq("type", type_filter)
        if category:
            q = q.eq("category", category)
        if priority:
            q = q.eq("priority", priority)
        if parent_id:
            q = q.eq("parent_id", parent_id)
        if keyword:
            q = q.or_(f"name.ilike.%{keyword}%,id.ilike.%{keyword}%")
        res = await q.execute()
        institutions = res.data or []

        # group 过滤（客户端派生，因为 DB 没有 group 列）
        # 支持聚合分组：group=高校 匹配 共建高校/兄弟院校/海外高校/其他高校
        if group:
            institutions = [
                i for i in institutions
                if _match_group(_derive_group(i.get("category")), group)
            ]

        if custom_field_key:
            institutions = [
                i for i in institutions
                if (i.get("custom_fields") or {}).get(custom_field_key) == custom_field_value
            ]

        institutions.sort(key=_institution_sort_key)
        total = len(institutions)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        items = [
            InstitutionListItem(
                id=i["id"], name=i["name"], type=i["type"],
                group=_derive_group(i.get("category")),
                category=i.get("category"),
                priority=f"P{i['priority']}" if i.get("priority") is not None else None,
                scholar_count=i.get("scholar_count", 0),
                student_count_total=i.get("student_count_total"),
                mentor_count=i.get("mentor_count"),
                parent_id=i.get("parent_id"),
            )
            for i in institutions[start: start + page_size]
        ]
        return InstitutionListResponse(total=total, page=page, page_size=page_size,
                                       total_pages=total_pages, items=items)
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB get_institution_list failed: %s", exc)

    data = _load_institutions()
    universities = data.get("universities", [])

    # 扁平化
    institutions = _flatten_institutions(universities)

    # 过滤
    filtered = institutions

    if type_filter:
        filtered = [i for i in filtered if i["type"] == type_filter]

    if group:
        filtered = [i for i in filtered if _match_group(_derive_group(i.get("category")), group)]

    if category:
        filtered = [i for i in filtered if i.get("category") == category]

    if priority:
        filtered = [i for i in filtered if i.get("priority") == priority]

    if parent_id:
        filtered = [i for i in filtered if i.get("parent_id") == parent_id]

    if keyword:
        kw = keyword.lower()
        filtered = [
            i for i in filtered
            if kw in i["name"].lower() or kw in i["id"].lower()
        ]

    filtered.sort(key=_institution_sort_key)

    # 分页
    total = len(filtered)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = start + page_size
    items = filtered[start:end]

    # 转换为 schema
    list_items = [
        InstitutionListItem(
            id=inst["id"],
            name=inst["name"],
            type=inst["type"],
            group=_derive_group(inst.get("category")),
            category=inst.get("category"),
            priority=inst.get("priority"),
            scholar_count=inst["scholar_count"],
            student_count_total=inst.get("student_count_total"),
            mentor_count=inst.get("mentor_count"),
            parent_id=inst.get("parent_id"),
        )
        for inst in items
    ]

    return InstitutionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=list_items,
    )


async def get_institution_detail(institution_id: str) -> InstitutionDetailResponse | None:
    """获取机构详情（高校或院系）."""
    # Try DB first
    try:
        client = _get_client()
        res = await client.table("institutions").select("*").eq("id", institution_id).execute()
        rows = res.data or []

        if rows:
            row = rows[0]
            if row.get("type") == "university":
                return _build_university_detail_from_db(row)
            else:
                return _build_department_detail_from_db(row)
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB get_institution_detail failed: %s", exc)

    data = _load_institutions()
    universities = data.get("universities", [])

    # 查找高校
    for univ in universities:
        if univ["id"] == institution_id:
            return _build_university_detail(univ, data.get("last_updated"))

        # 查找院系
        for dept in univ.get("departments", []):
            if dept["id"] == institution_id:
                return _build_department_detail(dept, univ["id"])

    return None


def _build_university_detail(univ: dict, last_updated: str | None = None) -> InstitutionDetailResponse:
    """构建高校详情响应."""
    # 数据直接存储在 univ 对象中，不在 details 字段

    # 解析学者信息（university_leaders 现在是字符串列表）
    university_leaders_raw = univ.get("university_leaders", [])
    university_leaders = []
    if isinstance(university_leaders_raw, list):
        for item in university_leaders_raw:
            if isinstance(item, str):
                university_leaders.append(ScholarInfo(name=item))
            elif isinstance(item, dict):
                university_leaders.append(ScholarInfo(**item))

    # 解析重要学者（notable_scholars 现在是字符串列表）
    notable_scholars_raw = univ.get("notable_scholars", [])
    notable_scholars = []
    if isinstance(notable_scholars_raw, list):
        for item in notable_scholars_raw:
            if isinstance(item, str):
                notable_scholars.append(ScholarInfo(name=item))
            elif isinstance(item, dict):
                notable_scholars.append(ScholarInfo(**item))

    # 解析导师信息（mentors 是对象列表）
    mentor_info = None
    mentors_list = univ.get("mentors", [])
    if mentors_list and len(mentors_list) > 0:
        # 取第一个导师作为 mentor_info
        first_mentor = mentors_list[0]
        mentor_info = MentorInfo(
            name=first_mentor.get("name"),
            category=first_mentor.get("category"),
            department=first_mentor.get("department")
        )

    # 解析院系信息
    departments = [
        DepartmentInfo(
            id=d["id"],
            name=d["name"],
            scholar_count=d.get("scholar_count", 0),
            sources=[DepartmentSource(**s) for s in d.get("sources", [])],
            org_name=d.get("org_name")
        )
        for d in univ.get("departments", [])
    ]

    return InstitutionDetailResponse(
        id=univ["id"],
        name=univ["name"],
        type="university",
        org_name=univ.get("org_name"),
        group=_derive_group(univ.get("category")),
        category=univ.get("category"),
        priority=univ.get("priority"),
        student_count_24=univ.get("student_count_24"),
        student_count_25=univ.get("student_count_25"),
        student_count_total=univ.get("student_count_total"),
        mentor_count=univ.get("mentor_count"),
        resident_leaders=univ.get("resident_leaders", []),
        degree_committee=univ.get("degree_committee", []),
        teaching_committee=univ.get("teaching_committee", []),
        mentor_info=mentor_info,
        university_leaders=university_leaders,
        notable_scholars=notable_scholars,
        key_departments=univ.get("key_departments", []),
        joint_labs=univ.get("joint_labs", []),
        training_cooperation=univ.get("training_cooperation", []),
        academic_cooperation=univ.get("academic_cooperation", []),
        talent_dual_appointment=univ.get("talent_dual_appointment", []),
        recruitment_events=univ.get("recruitment_events", []),
        visit_exchanges=univ.get("visit_exchanges", []),
        cooperation_focus=univ.get("cooperation_focus", []),
        parent_id=None,
        departments=departments,
        scholar_count=univ.get("scholar_count", 0),
        sources=[],
        last_updated=last_updated,
        custom_fields=univ.get("custom_fields") or {},
    )


def _build_department_detail(dept: dict, parent_id: str) -> InstitutionDetailResponse:
    """构建院系详情响应."""
    sources = [DepartmentSource(**s) for s in dept.get("sources", [])]

    return InstitutionDetailResponse(
        id=dept["id"],
        name=dept["name"],
        type="department",
        category=None,
        priority=None,
        student_count_24=None,
        student_count_25=None,
        student_count_total=None,
        mentor_count=None,
        resident_leaders=[],
        degree_committee=[],
        teaching_committee=[],
        mentor_info=None,
        university_leaders=[],
        notable_scholars=[],
        key_departments=[],
        joint_labs=[],
        training_cooperation=[],
        academic_cooperation=[],
        talent_dual_appointment=[],
        recruitment_events=[],
        visit_exchanges=[],
        cooperation_focus=[],
        parent_id=parent_id,
        departments=[],
        scholar_count=dept.get("scholar_count", 0),
        sources=sources,
        last_updated=None,
        custom_fields=dept.get("custom_fields") or {},
    )


def _build_university_detail_from_db(row: dict) -> InstitutionDetailResponse:
    """Build InstitutionDetailResponse from a DB institutions row (type=university)."""
    # Parse ScholarInfo lists
    def _parse_scholar_list(raw) -> list:
        if not raw:
            return []
        result = []
        for item in raw:
            if isinstance(item, str):
                result.append(ScholarInfo(name=item))
            elif isinstance(item, dict):
                result.append(ScholarInfo(**{k: v for k, v in item.items() if k in ("name", "url", "department")}))
        return result

    mentor_info = None
    mentors_list = row.get("mentors") or []
    if mentors_list:
        m = mentors_list[0]
        if isinstance(m, dict):
            mentor_info = MentorInfo(
                name=m.get("name"),
                category=m.get("category"),
                department=m.get("department"),
            )

    # Build departments list (fetch separately or use empty list)
    departments: list[DepartmentInfo] = []

    return InstitutionDetailResponse(
        id=row["id"],
        name=row["name"],
        type="university",
        org_name=row.get("org_name"),
        group=_derive_group(row.get("category")),
        category=row.get("category"),
        priority=f"P{row['priority']}" if row.get("priority") is not None else None,
        student_count_24=row.get("student_count_24"),
        student_count_25=row.get("student_count_25"),
        student_count_total=row.get("student_count_total"),
        mentor_count=row.get("mentor_count"),
        resident_leaders=row.get("resident_leaders") or [],
        degree_committee=row.get("degree_committee") or [],
        teaching_committee=row.get("teaching_committee") or [],
        mentor_info=mentor_info,
        university_leaders=_parse_scholar_list(row.get("university_leaders")),
        notable_scholars=_parse_scholar_list(row.get("notable_scholars")),
        key_departments=row.get("key_departments") or [],
        joint_labs=row.get("joint_labs") or [],
        training_cooperation=row.get("training_cooperation") or [],
        academic_cooperation=row.get("academic_cooperation") or [],
        talent_dual_appointment=row.get("talent_dual_appointment") or [],
        recruitment_events=row.get("recruitment_events") or [],
        visit_exchanges=row.get("visit_exchanges") or [],
        cooperation_focus=row.get("cooperation_focus") or [],
        parent_id=None,
        departments=departments,
        scholar_count=row.get("scholar_count", 0),
        sources=[],
        last_updated=None,
        custom_fields=row.get("custom_fields") or {},
    )


def _build_department_detail_from_db(row: dict) -> InstitutionDetailResponse:
    """Build InstitutionDetailResponse from a DB institutions row (type=department)."""
    sources_raw = row.get("sources") or []
    sources = []
    for s in sources_raw:
        if isinstance(s, dict):
            try:
                sources.append(DepartmentSource(**s))
            except Exception:
                pass

    return InstitutionDetailResponse(
        id=row["id"],
        name=row["name"],
        type="department",
        category=None,
        priority=None,
        student_count_24=None,
        student_count_25=None,
        student_count_total=None,
        mentor_count=None,
        resident_leaders=[],
        degree_committee=[],
        teaching_committee=[],
        mentor_info=None,
        university_leaders=[],
        notable_scholars=[],
        key_departments=[],
        joint_labs=[],
        training_cooperation=[],
        academic_cooperation=[],
        talent_dual_appointment=[],
        recruitment_events=[],
        visit_exchanges=[],
        cooperation_focus=[],
        parent_id=row.get("parent_id"),
        departments=[],
        scholar_count=row.get("scholar_count", 0),
        sources=sources,
        last_updated=None,
        custom_fields=row.get("custom_fields") or {},
    )


async def get_institution_stats() -> InstitutionStatsResponse:
    """获取机构统计信息."""
    try:
        client = _get_client()
        res = await client.table("institutions").select(
            "type,category,priority,scholar_count,student_count_total,mentor_count"
        ).execute()
        rows = res.data or []

        unis = [r for r in rows if r.get("type") == "university"]
        depts = [r for r in rows if r.get("type") == "department"]
        by_category: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for r in unis:
            cat = r.get("category") or "未分类"
            by_category[cat] = by_category.get(cat, 0) + 1
            raw_pri = r.get("priority")
            pri = f"P{raw_pri}" if raw_pri is not None else "未设置"
            by_priority[pri] = by_priority.get(pri, 0) + 1
        return InstitutionStatsResponse(
            total_universities=len(unis),
            total_departments=len(depts),
            total_scholars=sum(r.get("scholar_count", 0) or 0 for r in unis),
            by_category=[{"category": k, "count": v} for k, v in by_category.items()],
            by_priority=[{"priority": k, "count": v} for k, v in by_priority.items()],
            total_students=sum(r.get("student_count_total", 0) or 0 for r in unis),
            total_mentors=sum(r.get("mentor_count", 0) or 0 for r in unis),
        )
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB get_institution_stats failed: %s", exc)

    data = _load_institutions()
    universities = data.get("universities", [])

    total_universities = len(universities)
    total_departments = sum(len(u.get("departments", [])) for u in universities)
    total_scholars = sum(u.get("scholar_count", 0) for u in universities)

    # 按分类统计（数据直接在 univ 对象中）
    by_category: dict[str, int] = {}
    for univ in universities:
        cat = univ.get("category", "未分类")
        if cat:
            by_category[cat] = by_category.get(cat, 0) + 1

    # 按优先级统计（数据直接在 univ 对象中）
    by_priority: dict[str, int] = {}
    for univ in universities:
        pri = univ.get("priority", "未设置")
        if pri:
            by_priority[pri] = by_priority.get(pri, 0) + 1

    # 学生和导师总数（数据直接在 univ 对象中）
    total_students = sum(
        univ.get("student_count_total", 0) or 0
        for univ in universities
    )
    total_mentors = sum(
        univ.get("mentor_count", 0) or 0
        for univ in universities
    )

    return InstitutionStatsResponse(
        total_universities=total_universities,
        total_departments=total_departments,
        total_scholars=total_scholars,
        by_category=[{"category": k, "count": v} for k, v in by_category.items()],
        by_priority=[{"priority": k, "count": v} for k, v in by_priority.items()],
        total_students=total_students,
        total_mentors=total_mentors,
    )


async def create_institution(inst_data: dict[str, Any]) -> InstitutionDetailResponse:
    """创建新机构（高校或院系），支持三种场景."""
    from app.services.core.id_generator import (  # noqa: PLC0415
        generate_institution_id,
        is_valid_institution_id,
    )

    client = _get_client()
    inst_type = inst_data.get("type", "university")
    inst_name = inst_data.get("name")
    if not inst_name:
        raise ValueError("Institution name is required")

    inst_id = inst_data.get("id")
    if not inst_id:
        inst_id = generate_institution_id(inst_name)
    elif not is_valid_institution_id(inst_id):
        raise ValueError(f"Invalid institution ID format: '{inst_id}'.")

    # 重复检测
    check = await client.table("institutions").select("id").eq("id", inst_id).execute()
    if check.data:
        raise InstitutionAlreadyExistsError(f"机构 '{inst_id}'（{inst_name}）已存在")

    student_count_24 = inst_data.get("student_count_24") or 0
    student_count_25 = inst_data.get("student_count_25") or 0

    if inst_type == "university":
        row: dict[str, Any] = {
            "id": inst_id, "name": inst_name, "type": "university",
            "org_name": inst_data.get("org_name"),
            "scholar_count": 0,
            "category": inst_data.get("category"),
            "priority": inst_data.get("priority"),
            "student_count_24": student_count_24,
            "student_count_25": student_count_25,
            "student_count_total": student_count_24 + student_count_25,
            "mentor_count": inst_data.get("mentor_count") or 0,
            "resident_leaders": inst_data.get("resident_leaders") or [],
            "degree_committee": inst_data.get("degree_committee") or [],
            "teaching_committee": inst_data.get("teaching_committee") or [],
            "university_leaders": inst_data.get("university_leaders") or [],
            "notable_scholars": inst_data.get("notable_scholars") or [],
            "key_departments": inst_data.get("key_departments") or [],
            "joint_labs": inst_data.get("joint_labs") or [],
            "training_cooperation": inst_data.get("training_cooperation") or [],
            "academic_cooperation": inst_data.get("academic_cooperation") or [],
            "talent_dual_appointment": inst_data.get("talent_dual_appointment") or [],
            "recruitment_events": inst_data.get("recruitment_events") or [],
            "visit_exchanges": inst_data.get("visit_exchanges") or [],
            "cooperation_focus": inst_data.get("cooperation_focus") or [],
            "custom_fields": inst_data.get("custom_fields") or {},
        }
        res = await client.table("institutions").insert(row).execute()
        created = res.data[0] if res.data else row

        # 场景 3: 同时创建院系
        departments_input = inst_data.get("departments") or []
        for dept_input in departments_input:
            dept_name = dept_input.get("name")
            if not dept_name:
                continue
            dept_id = dept_input.get("id") or generate_institution_id(dept_name)
            await client.table("institutions").insert({
                "id": dept_id, "name": dept_name, "type": "department",
                "parent_id": inst_id, "org_name": dept_input.get("org_name"), "scholar_count": 0,
            }).execute()

        return _build_university_detail_from_db(created)

    else:  # department
        parent_id = inst_data.get("parent_id")
        if not parent_id:
            raise ValueError("创建院系时 parent_id 为必填项")
        parent_check = await client.table("institutions").select("id").eq("id", parent_id).execute()
        if not parent_check.data:
            raise ValueError(f"父高校 '{parent_id}' 不存在")

        row = {
            "id": inst_id, "name": inst_name, "type": "department",
            "parent_id": parent_id, "org_name": inst_data.get("org_name"), "scholar_count": 0,
        }
        res = await client.table("institutions").insert(row).execute()
        created = res.data[0] if res.data else row
        return _build_department_detail_from_db(created)


async def update_institution(
    institution_id: str, updates: dict[str, Any]
) -> InstitutionDetailResponse | None:
    """更新机构信息（DB）."""
    from app.services.core.custom_fields import apply_custom_fields_update  # noqa: PLC0415

    client = _get_client()

    # custom_fields 浅合并
    if "custom_fields" in updates:
        tbl = client.table("institutions")
        cur = await tbl.select("custom_fields").eq("id", institution_id).execute()
        if cur.data:
            apply_custom_fields_update(updates, cur.data[0])
        else:
            return None

    # 重新计算学生总数
    if "student_count_24" in updates or "student_count_25" in updates:
        # Get current values first
        cur = await client.table("institutions").select(
            "student_count_24,student_count_25"
        ).eq("id", institution_id).execute()
        if cur.data:
            cur_row = cur.data[0]
            sc24 = updates.get("student_count_24", cur_row.get("student_count_24") or 0) or 0
            sc25 = updates.get("student_count_25", cur_row.get("student_count_25") or 0) or 0
            updates["student_count_total"] = sc24 + sc25

    res = await client.table("institutions").update(updates).eq("id", institution_id).select("*").execute()
    if not res.data:
        return None
    row = res.data[0]
    if row.get("type") == "university":
        return _build_university_detail_from_db(row)
    return _build_department_detail_from_db(row)


async def delete_institution(institution_id: str) -> bool:
    """删除机构（DB）."""
    client = _get_client()
    exist = await client.table("institutions").select("id").eq("id", institution_id).execute()
    if not exist.data:
        return False
    await client.table("institutions").delete().eq("id", institution_id).execute()
    return True


# ---------------------------------------------------------------------------
# AMiner integration helpers
# ---------------------------------------------------------------------------


def search_institutions_for_aminer(name: str) -> list[dict]:
    """Search institutions by name for AMiner integration (fuzzy match).

    Args:
        name: Search query (case-insensitive, substring match)

    Returns:
        List of matching university dicts
    """
    if not name or not name.strip():
        return []

    query = name.strip().lower()
    data = _load_institutions()
    universities = data.get("universities", [])

    matches = []
    for univ in universities:
        name_zh = univ.get("name", "").lower()
        if query in name_zh:
            matches.append(univ)

    return matches


# ---------------------------------------------------------------------------
# Scholar Institutions API helpers
# ---------------------------------------------------------------------------


async def _fetch_all_institutions_from_db() -> list[dict]:
    """Fetch all rows from institutions table."""
    client = _get_client()
    res = await client.table("institutions").select("*").execute()
    return res.data or []


async def get_institution_tree() -> Any:
    """返回机构分类树（group → category → institution → departments）。

    供前端侧边栏使用，按照后端 category/group 体系分类，不再依赖名称启发式推断。
    """
    from app.schemas.institution import (  # noqa: PLC0415
        InstitutionTreeCategory,
        InstitutionTreeDepartment,
        InstitutionTreeGroup,
        InstitutionTreeInstitution,
        InstitutionTreeResponse,
    )

    try:
        client = _get_client()
        res = await client.table("institutions").select(
            "id,name,type,category,priority,scholar_count,parent_id"
        ).execute()
        rows = res.data or []
    except Exception as exc:
        import logging as _log  # noqa: PLC0415
        _log.getLogger(__name__).warning("DB get_institution_tree failed: %s", exc)
        data = _load_institutions()
        rows = _flatten_institutions(data.get("universities", []))

    unis = [r for r in rows if r.get("type") == "university"]
    depts = [r for r in rows if r.get("type") == "department"]

    # Build university → departments map
    dept_map: dict[str, list[dict]] = {}
    for d in depts:
        pid = d.get("parent_id")
        if pid:
            dept_map.setdefault(pid, []).append({
                "name": d["name"],
                "scholar_count": d.get("scholar_count", 0),
            })

    # Group unis: group → category → [institution, ...]
    tree: dict[str, dict[str, list]] = {}
    for uni in unis:
        cat = uni.get("category") or ""
        group = _derive_group(cat) or "其他高校"
        tree.setdefault(group, {}).setdefault(cat, []).append({
            "id": uni["id"],
            "name": uni["name"],
            "scholar_count": uni.get("scholar_count", 0),
            "departments": sorted(
                dept_map.get(uni["id"], []),
                key=lambda d: -d["scholar_count"],
            ),
        })

    # Sort institutions within each category by prestige → scholar count → name
    for cats_map in tree.values():
        for insts in cats_map.values():
            insts.sort(key=lambda i: (
                _INSTITUTION_PRESTIGE_ORDER.get(i["id"], 999),
                -i["scholar_count"],
                i["name"],
            ))

    # Build response
    groups_list = []
    for group, cats_map in sorted(tree.items(), key=lambda kv: _GROUP_ORDER.get(kv[0], 99)):
        categories_list = []
        for cat, insts in sorted(cats_map.items(), key=lambda kv: _CATEGORY_ORDER.get(kv[0], 99)):
            cat_count = sum(i["scholar_count"] for i in insts)
            categories_list.append(InstitutionTreeCategory(
                category=cat,
                scholar_count=cat_count,
                institutions=[
                    InstitutionTreeInstitution(
                        id=i["id"],
                        name=i["name"],
                        scholar_count=i["scholar_count"],
                        departments=[InstitutionTreeDepartment(**d) for d in i["departments"]],
                    )
                    for i in insts
                ],
            ))
        group_count = sum(c.scholar_count for c in categories_list)
        groups_list.append(InstitutionTreeGroup(
            group=group,
            scholar_count=group_count,
            categories=categories_list,
        ))

    total = sum(g.scholar_count for g in groups_list)
    return InstitutionTreeResponse(total_scholar_count=total, groups=groups_list)


async def get_scholar_institutions_list(
    keyword: str | None = None,
    region: str | None = None,
    affiliation_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Get paginated list of universities with departments (from DB).

    Args:
        region: 国内 | 国际（根据机构名称自动推断）
        affiliation_type: 高校 | 企业 | 研究机构 | 其他（根据机构名称自动推断）
    """
    import math

    from app.services.scholar._filters import (  # noqa: PLC0415
        _derive_affiliation_type_from_university,
        _derive_region_from_university,
    )

    rows = await _fetch_all_institutions_from_db()
    unis = {r["id"]: r for r in rows if r.get("type") == "university"}
    depts = [r for r in rows if r.get("type") == "department"]

    # Attach departments to their parent university
    for d in depts:
        pid = d.get("parent_id")
        if pid and pid in unis:
            unis[pid].setdefault("departments", []).append({
                "id": d["id"],
                "name": d["name"],
                "scholar_count": d.get("scholar_count", 0),
                "org_name": d.get("org_name"),
            })

    university_list = list(unis.values())

    if keyword:
        kw = keyword.lower()
        university_list = [
            u for u in university_list
            if kw in u.get("name", "").lower()
            or kw in u.get("id", "").lower()
        ]

    if region:
        university_list = [
            u for u in university_list
            if _derive_region_from_university(u.get("name", "")) == region
        ]

    if affiliation_type:
        university_list = [
            u for u in university_list
            if _derive_affiliation_type_from_university(
                u.get("name", "")
            ) == affiliation_type
        ]

    total = len(university_list)
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    start = (page - 1) * page_size
    page_items = [
        {
            "id": u["id"],
            "name": u["name"],
            "scholar_count": u.get("scholar_count", 0),
            "departments": u.get("departments", []),
            "org_name": u.get("org_name"),
        }
        for u in university_list[start: start + page_size]
    ]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": page_items,
    }


async def get_scholar_institution_detail(university_id: str) -> dict[str, Any] | None:
    """Get single university with all departments (from DB)."""
    rows = await _fetch_all_institutions_from_db()
    uni = next((r for r in rows if r["id"] == university_id and r.get("type") == "university"), None)
    if not uni:
        return None
    depts = [
        {"id": r["id"], "name": r["name"], "scholar_count": r.get("scholar_count", 0), "org_name": r.get("org_name")}
        for r in rows if r.get("type") == "department" and r.get("parent_id") == university_id
    ]
    return {**uni, "departments": depts}


async def get_scholar_department_detail(
    university_id: str,
    department_id: str,
) -> dict[str, Any] | None:
    """Get single department (from DB)."""
    client = _get_client()
    res = await client.table("institutions").select("*").eq("id", department_id).execute()
    rows = res.data or []
    for r in rows:
        if r.get("parent_id") == university_id:
            return r
    return None


async def get_scholar_institutions_stats(
    region: str | None = None,
    affiliation_type: str | None = None,
) -> dict[str, Any]:
    """Get overall statistics (from DB), optionally filtered by region/affiliation_type."""
    from app.services.scholar._filters import (  # noqa: PLC0415
        _derive_affiliation_type_from_university,
        _derive_region_from_university,
    )

    rows = await _fetch_all_institutions_from_db()
    unis = [r for r in rows if r.get("type") == "university"]
    depts = [r for r in rows if r.get("type") == "department"]

    if region:
        unis = [
            u for u in unis
            if _derive_region_from_university(u.get("name", "")) == region
        ]
        uni_ids = {u["id"] for u in unis}
        depts = [d for d in depts if d.get("parent_id") in uni_ids]

    if affiliation_type:
        unis = [
            u for u in unis
            if _derive_affiliation_type_from_university(
                u.get("name", "")
            ) == affiliation_type
        ]
        uni_ids = {u["id"] for u in unis}
        depts = [d for d in depts if d.get("parent_id") in uni_ids]

    return {
        "total_universities": len(unis),
        "total_departments": len(depts),
        "total_scholars": sum(
            u.get("scholar_count", 0) or 0 for u in unis
        ),
    }
