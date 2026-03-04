"""Institution service — CRUD operations for institutions data."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.schemas.institution import (
    InstitutionDetailResponse,
    InstitutionListItem,
    InstitutionListResponse,
    InstitutionStatsResponse,
)

INSTITUTIONS_FILE = Path("data/institutions.json")


def _load_institutions() -> dict[str, Any]:
    """Load institutions data from JSON file."""
    if not INSTITUTIONS_FILE.exists():
        return {"total": 0, "last_updated": None, "institutions": []}

    with open(INSTITUTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_institutions(data: dict[str, Any]) -> None:
    """Save institutions data to JSON file."""
    data["last_updated"] = datetime.now().isoformat()
    with open(INSTITUTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_institution_list(
    category: str | None = None,
    priority: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> InstitutionListResponse:
    """Get paginated list of institutions with filtering."""
    data = _load_institutions()
    institutions = data.get("institutions", [])

    # Apply filters
    filtered = institutions

    if category:
        filtered = [i for i in filtered if i.get("category", "") == category]

    if priority:
        filtered = [i for i in filtered if i.get("priority", "") == priority]

    if keyword:
        kw = keyword.lower()
        filtered = [
            i for i in filtered
            if kw in i.get("name", "").lower()
            or kw in i.get("id", "").lower()
            or any(kw in dept.lower() for dept in i.get("key_departments", []))
        ]

    # Sort by priority (P0 > P1 > P2 > P3) then by name
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    filtered.sort(
        key=lambda x: (
            priority_order.get(x.get("priority", "P3"), 99),
            x.get("name", "")
        )
    )

    # Pagination
    total = len(filtered)
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    end = start + page_size
    items = filtered[start:end]

    # Convert to list items
    list_items = [
        InstitutionListItem(
            id=inst.get("id", ""),
            name=inst.get("name", ""),
            category=inst.get("category", ""),
            priority=inst.get("priority", ""),
            is_demo_school=inst.get("is_demo_school", False),
            student_count_24=inst.get("student_count_24", 0),
            student_count_25=inst.get("student_count_25", 0),
            student_count_total=inst.get("student_count_total", 0),
            supervisor_count=inst.get("supervisor_count", 0),
            collaboration_focus=inst.get("collaboration_focus", ""),
            key_departments=inst.get("key_departments", []),
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
    """Get detailed information for a single institution."""
    data = _load_institutions()
    institutions = data.get("institutions", [])

    for inst in institutions:
        if inst.get("id") == institution_id:
            return InstitutionDetailResponse(**inst)

    return None


def get_institution_stats() -> InstitutionStatsResponse:
    """Get statistics for all institutions."""
    data = _load_institutions()
    institutions = data.get("institutions", [])

    # Basic counts
    total = len(institutions)
    demo_schools = sum(1 for i in institutions if i.get("is_demo_school", False))
    total_students = sum(i.get("student_count_total", 0) for i in institutions)
    total_supervisors = sum(i.get("supervisor_count", 0) for i in institutions)

    # By category
    by_category: dict[str, int] = {}
    for inst in institutions:
        cat = inst.get("category", "未分类")
        by_category[cat] = by_category.get(cat, 0) + 1

    # By priority
    by_priority: dict[str, int] = {}
    for inst in institutions:
        pri = inst.get("priority", "未设置")
        by_priority[pri] = by_priority.get(pri, 0) + 1

    # By collaboration focus
    by_focus: dict[str, int] = {}
    for inst in institutions:
        focus = inst.get("collaboration_focus", "未设置")
        if focus:
            by_focus[focus] = by_focus.get(focus, 0) + 1

    return InstitutionStatsResponse(
        total=total,
        demo_schools=demo_schools,
        by_category=[{"category": k, "count": v} for k, v in by_category.items()],
        by_priority=[{"priority": k, "count": v} for k, v in by_priority.items()],
        total_students=total_students,
        total_supervisors=total_supervisors,
        by_collaboration_focus=[{"focus": k, "count": v} for k, v in by_focus.items()],
    )


def create_institution(inst_data: dict[str, Any]) -> InstitutionDetailResponse:
    """Create a new institution."""
    data = _load_institutions()
    institutions = data.get("institutions", [])

    # Check if ID already exists
    if any(i.get("id") == inst_data.get("id") for i in institutions):
        raise ValueError(f"Institution with ID '{inst_data['id']}' already exists")

    # Add timestamps
    now = datetime.now().isoformat()
    inst_data["created_at"] = now
    inst_data["updated_at"] = now
    inst_data["last_updated"] = now
    inst_data["data_source"] = "manual"

    # Calculate total student count
    inst_data["student_count_total"] = (
        inst_data.get("student_count_24", 0) + inst_data.get("student_count_25", 0)
    )

    institutions.append(inst_data)
    data["institutions"] = institutions
    data["total"] = len(institutions)

    _save_institutions(data)

    return InstitutionDetailResponse(**inst_data)


def update_institution(
    institution_id: str, updates: dict[str, Any]
) -> InstitutionDetailResponse | None:
    """Update an existing institution."""
    data = _load_institutions()
    institutions = data.get("institutions", [])

    for i, inst in enumerate(institutions):
        if inst.get("id") == institution_id:
            # Apply updates
            for key, value in updates.items():
                if key != "id":  # Don't allow ID changes
                    inst[key] = value

            # Update timestamp
            inst["updated_at"] = datetime.now().isoformat()

            # Recalculate total if counts changed
            if "student_count_24" in updates or "student_count_25" in updates:
                inst["student_count_total"] = (
                    inst.get("student_count_24", 0) + inst.get("student_count_25", 0)
                )

            institutions[i] = inst
            data["institutions"] = institutions

            _save_institutions(data)

            return InstitutionDetailResponse(**inst)

    return None


def delete_institution(institution_id: str) -> bool:
    """Delete an institution."""
    data = _load_institutions()
    institutions = data.get("institutions", [])

    original_count = len(institutions)
    institutions = [i for i in institutions if i.get("id") != institution_id]

    if len(institutions) < original_count:
        data["institutions"] = institutions
        data["total"] = len(institutions)
        _save_institutions(data)
        return True

    return False


# ---------------------------------------------------------------------------
# AMiner integration helpers
# ---------------------------------------------------------------------------


def search_institutions_for_aminer(name: str) -> list[dict]:
    """Search institutions by name for AMiner integration (fuzzy match on name_zh).

    Args:
        name: Search query (case-insensitive, substrg match)

    Returns:
        List of matching organization dicts with AMiner-specific fields
        (name_zh, name_en, org_id, org_name, category, priority)
    """
    if not name or not name.strip():
        return []

    query = name.strip().lower()
    data = _load_institutions()
    institutions = data.get("institutions", [])

    matches = []
    for inst in institutions:
        name_zh = inst.get("name", "").lower()
        if query in name_zh:
            matches.append(inst)

    return matches
