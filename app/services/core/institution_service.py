"""Institution service — 统一的机构（高校+院系）CRUD 操作."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.institution import (
    InstitutionDetailResponse,
    InstitutionListItem,
    InstitutionListResponse,
    InstitutionStatsResponse,
    ScholarInfo,
    MentorInfo,
    DepartmentInfo,
    DepartmentSource,
)

INSTITUTIONS_FILE = Path("data/scholars/institutions.json")


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


def get_institution_list(
    type_filter: str | None = None,  # 'university' | 'department'
    category: str | None = None,
    priority: str | None = None,
    parent_id: str | None = None,  # 筛选某高校下的院系
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> InstitutionListResponse:
    """获取机构列表（高校+院系统一查询）."""
    # Try DB first
    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()

        async def _fetch():
            q = client.table("institutions").select(
                "id,name,type,category,priority,scholar_count,student_count_total,mentor_count,parent_id"
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
            return res.data or []

        institutions = asyncio.get_event_loop().run_until_complete(_fetch())
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        institutions.sort(key=lambda x: (
            0 if x["type"] == "university" else 1,
            priority_order.get(str(x.get("priority") or ""), 99),
            x["name"],
        ))
        total = len(institutions)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        items = [
            InstitutionListItem(
                id=i["id"], name=i["name"], type=i["type"],
                category=i.get("category"), priority=str(i["priority"]) if i.get("priority") else None,
                scholar_count=i.get("scholar_count", 0),
                student_count_total=i.get("student_count_total"),
                mentor_count=i.get("mentor_count"),
                parent_id=i.get("parent_id"),
            )
            for i in institutions[start: start + page_size]
        ]
        return InstitutionListResponse(total=total, page=page, page_size=page_size,
                                       total_pages=total_pages, items=items)
    except RuntimeError:
        pass
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

    # 排序：高校按优先级，院系按名称
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    filtered.sort(
        key=lambda x: (
            0 if x["type"] == "university" else 1,
            priority_order.get(x.get("priority", ""), 99),
            x["name"]
        )
    )

    # 分页
    total = len(filtered)
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    end = start + page_size
    items = filtered[start:end]

    # 转换为 schema
    list_items = [
        InstitutionListItem(
            id=inst["id"],
            name=inst["name"],
            type=inst["type"],
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


def get_institution_detail(institution_id: str) -> InstitutionDetailResponse | None:
    """获取机构详情（高校或院系）."""
    # Try DB first
    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()

        async def _fetch():
            res = await client.table("institutions").select("*").eq("id", institution_id).execute()
            return res.data or []

        rows = asyncio.get_event_loop().run_until_complete(_fetch())
        if rows:
            row = rows[0]
            if row.get("type") == "university":
                return _build_university_detail_from_db(row)
            else:
                return _build_department_detail_from_db(row)
    except RuntimeError:
        pass
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
        category=row.get("category"),
        priority=str(row["priority"]) if row.get("priority") is not None else None,
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
    )


def get_institution_stats() -> InstitutionStatsResponse:
    """获取机构统计信息."""
    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()

        async def _fetch():
            res = await client.table("institutions").select(
                "type,category,priority,scholar_count,student_count_total,mentor_count"
            ).execute()
            return res.data or []

        rows = asyncio.get_event_loop().run_until_complete(_fetch())
        unis = [r for r in rows if r.get("type") == "university"]
        depts = [r for r in rows if r.get("type") == "department"]
        by_category: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for r in unis:
            cat = r.get("category") or "未分类"
            by_category[cat] = by_category.get(cat, 0) + 1
            pri = str(r.get("priority") or "未设置")
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
    except RuntimeError:
        pass
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


def create_institution(inst_data: dict[str, Any]) -> InstitutionDetailResponse:
    """创建新机构（高校或院系），支持三种场景：

    场景 1: 仅创建高校（type='university', departments=None 或 []）
    场景 2: 仅创建院系（type='department', parent_id 必填）
    场景 3: 创建高校 + 院系（type='university', departments=[...] 非空）

    Args:
        inst_data: Institution data dict with name, type, and optional id/parent_id/etc.
                  If 'id' is not provided, it will be auto-generated from 'name'.

    Raises:
        InstitutionAlreadyExistsError: 机构 ID 已存在。
        ValueError: 参数校验失败（如 department 缺少 parent_id）。
    """
    from app.services.core.id_generator import generate_institution_id, is_valid_institution_id

    data = _load_institutions()
    universities = data.get("universities", [])

    inst_type = inst_data.get("type", "university")
    inst_name = inst_data.get("name")
    if not inst_name:
        raise ValueError("Institution name is required")

    # Auto-generate ID if not provided
    inst_id = inst_data.get("id")
    if not inst_id:
        inst_id = generate_institution_id(inst_name)
    elif not is_valid_institution_id(inst_id):
        raise ValueError(f"Invalid institution ID format: '{inst_id}'. Must be alphanumeric, lowercase, 2-30 chars")

    student_count_24 = inst_data.get("student_count_24") or 0
    student_count_25 = inst_data.get("student_count_25") or 0

    if inst_type == "university":
        # 重复检测 → 409
        if any(u["id"] == inst_id for u in universities):
            raise InstitutionAlreadyExistsError(
                f"高校 '{inst_id}'（{inst_data['name']}）已存在，请勿重复创建"
            )

        # 创建高校（扁平结构，与现有 JSON 保持一致）
        new_univ: dict[str, Any] = {
            "id": inst_id,
            "name": inst_data["name"],
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
            "mentors": [],
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
            "departments": [],
        }

        # 场景 3: 同时创建院系（如果提供了 departments 列表）
        departments_input = inst_data.get("departments")
        if departments_input:
            # Auto-generate dept IDs if not provided
            processed_depts = []
            generated_ids_set = set()
            for idx, dept_input in enumerate(departments_input, 1):
                dept_name = dept_input.get("name")
                if not dept_name:
                    raise ValueError("Department name is required in departments list")

                dept_id = dept_input.get("id")
                if not dept_id:
                    # Generate base ID from dept name
                    base_id = generate_institution_id(dept_name)
                    # If collision with other generated IDs, append index
                    if base_id in generated_ids_set:
                        dept_id = f"{base_id}_{idx}"
                    else:
                        dept_id = base_id
                elif not is_valid_institution_id(dept_id):
                    raise ValueError(f"Invalid department ID format: '{dept_id}'")

                generated_ids_set.add(dept_id)
                processed_depts.append((dept_id, dept_name, dept_input.get("org_name")))

            # 检查院系 ID 重复
            dept_ids = [d[0] for d in processed_depts]
            if len(dept_ids) != len(set(dept_ids)):
                raise ValueError("院系 ID 列表中存在重复")

            # 检查院系 ID 是否与其他高校的院系冲突，并创建院系
            for dept_id, dept_name, dept_org_name in processed_depts:
                # 检查全局院系 ID 冲突
                for existing_univ in universities:
                    for existing_dept in existing_univ.get("departments", []):
                        if existing_dept["id"] == dept_id:
                            raise InstitutionAlreadyExistsError(
                                f"院系 '{dept_id}'（{dept_name}）已存在于高校 "
                                f"'{existing_univ['id']}' 中，请使用不同的 ID"
                            )

                # 创建院系
                new_dept: dict[str, Any] = {
                    "id": dept_id,
                    "name": dept_name,
                    "org_name": dept_org_name,
                    "scholar_count": 0,
                    "sources": [],
                }
                new_univ["departments"].append(new_dept)

        universities.append(new_univ)
        data["universities"] = universities
        _save_institutions(data)

        return _build_university_detail(new_univ)

    else:  # department (场景 2)
        parent_id = inst_data.get("parent_id")
        if not parent_id:
            raise ValueError("创建院系时 parent_id（所属高校 ID）为必填项")

        # 查找父高校
        parent_univ = None
        for univ in universities:
            if univ["id"] == parent_id:
                parent_univ = univ
                break

        if not parent_univ:
            raise ValueError(f"父高校 '{parent_id}' 不存在")

        # 重复检测 → 409（检查该高校下的院系）
        if any(d["id"] == inst_id for d in parent_univ.get("departments", [])):
            raise InstitutionAlreadyExistsError(
                f"院系 '{inst_id}'（{inst_name}）已存在于高校 '{parent_id}' 中，请勿重复创建"
            )

        # 检查全局院系 ID 冲突（院系 ID 必须全局唯一）
        for univ in universities:
            for dept in univ.get("departments", []):
                if dept["id"] == inst_id:
                    raise InstitutionAlreadyExistsError(
                        f"院系 '{inst_id}'（{inst_name}）已存在于高校 '{univ['id']}' 中，"
                        "院系 ID 必须全局唯一"
                    )

        # 创建院系
        new_dept: dict[str, Any] = {
            "id": inst_id,
            "name": inst_name,
            "org_name": inst_data.get("org_name"),
            "scholar_count": 0,
            "sources": [],
        }
        parent_univ.setdefault("departments", []).append(new_dept)
        _save_institutions(data)

        return _build_department_detail(new_dept, parent_id)


def update_institution(
    institution_id: str, updates: dict[str, Any]
) -> InstitutionDetailResponse | None:
    """更新机构信息."""
    data = _load_institutions()
    universities = data.get("universities", [])

    # 查找并更新高校
    for univ in universities:
        if univ["id"] == institution_id:
            # 扁平结构写入（与 JSON 存储格式一致）
            flat_keys = [
                "name", "org_name", "category", "priority",
                "student_count_24", "student_count_25",
                "mentor_count", "resident_leaders", "degree_committee",
                "teaching_committee", "university_leaders", "notable_scholars",
                "key_departments", "joint_labs", "training_cooperation",
                "academic_cooperation", "talent_dual_appointment",
                "recruitment_events", "visit_exchanges", "cooperation_focus",
            ]
            for key, value in updates.items():
                if key in flat_keys:
                    univ[key] = value

            # 重新计算学生总数
            if "student_count_24" in updates or "student_count_25" in updates:
                univ["student_count_total"] = (
                    univ.get("student_count_24") or 0
                ) + (univ.get("student_count_25") or 0)

            _save_institutions(data)
            return _build_university_detail(univ)

        # 查找并更新院系
        for dept in univ.get("departments", []):
            if dept["id"] == institution_id:
                if "name" in updates:
                    dept["name"] = updates["name"]

                _save_institutions(data)
                return _build_department_detail(dept, univ["id"])

    return None


def delete_institution(institution_id: str) -> bool:
    """删除机构."""
    data = _load_institutions()
    universities = data.get("universities", [])

    # 删除高校
    original_count = len(universities)
    universities = [u for u in universities if u["id"] != institution_id]

    if len(universities) < original_count:
        data["universities"] = universities
        _save_institutions(data)
        return True

    # 删除院系
    for univ in universities:
        depts = univ.get("departments", [])
        original_dept_count = len(depts)
        depts = [d for d in depts if d["id"] != institution_id]

        if len(depts) < original_dept_count:
            univ["departments"] = depts
            # 重新计算高校学者总数
            univ["scholar_count"] = sum(d.get("scholar_count", 0) for d in depts)
            _save_institutions(data)
            return True

    return False


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


def get_scholar_institutions_list(
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Get paginated list of universities with departments and scholar counts.

    Args:
        keyword: Filter universities by name (case-insensitive substring match)
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        {
            "total": int,
            "page": int,
            "page_size": int,
            "total_pages": int,
            "items": [universities]
        }
    """
    import math

    data = _load_institutions()
    universities = data.get("universities", [])

    # Filter by keyword if provided
    if keyword:
        keyword_lower = keyword.lower()
        universities = [
            u for u in universities
            if keyword_lower in u.get("name", "").lower()
            or keyword_lower in u.get("id", "").lower()
        ]

    total = len(universities)
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    start = (page - 1) * page_size
    page_items = universities[start : start + page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": page_items,
    }


def get_scholar_institution_detail(university_id: str) -> dict[str, Any] | None:
    """Get single university with all departments and sources.

    Args:
        university_id: University ID (e.g., 'tsinghua')

    Returns:
        University object with departments, or None if not found
    """
    data = _load_institutions()
    universities = data.get("universities", [])

    for uni in universities:
        if uni.get("id") == university_id:
            return uni

    return None


def get_scholar_department_detail(
    university_id: str,
    department_id: str,
) -> dict[str, Any] | None:
    """Get single department with all sources.

    Args:
        university_id: University ID
        department_id: Department ID

    Returns:
        Department object with sources, or None if not found
    """
    uni = get_scholar_institution_detail(university_id)
    if not uni:
        return None

    for dept in uni.get("departments", []):
        if dept.get("id") == department_id:
            return dept

    return None


def get_scholar_institutions_stats() -> dict[str, Any]:
    """Get overall statistics about scholar institutions.

    Returns:
        {
            "total_universities": int,
            "total_departments": int,
            "total_scholars": int,
        }
    """
    data = _load_institutions()
    universities = data.get("universities", [])

    total_universities = len(universities)
    total_departments = 0
    total_scholars = 0

    for uni in universities:
        departments = uni.get("departments", [])
        total_departments += len(departments)
        total_scholars += uni.get("scholar_count", 0)

    return {
        "total_universities": total_universities,
        "total_departments": total_departments,
        "total_scholars": total_scholars,
    }
