"""Scholar service — public API for loading, filtering, and updating scholar data.

Internal implementation is split across private sub-modules:
  _data.py         — unified scholars.json loading and annotation merging
  _filters.py      — multi-field filtering helpers
  _transformers.py — response shape converters (_to_list_item, _to_detail)
"""
from __future__ import annotations

import json
import math
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from app.services.stores import scholar_annotation_store as annotation_store
from app.services.stores import supervised_student_store as student_store
from app.services.scholar._data import (
    SCHOLARS_FILE,
    _find_raw_file_by_hash,
    _load_all_with_annotations,
)
from app.services.scholar._filters import _apply_filters
from app.services.scholar._transformers import _to_detail, _to_list_item
from app.services.scholar._create import create_scholar, import_scholars_excel  # noqa: F401


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------


def get_scholar_list(
    *,
    university: str | None = None,
    department: str | None = None,
    position: str | None = None,
    is_academician: bool | None = None,
    is_potential_recruit: bool | None = None,
    is_advisor_committee: bool | None = None,
    has_email: bool | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    items = _load_all_with_annotations()

    filtered = _apply_filters(
        items,
        university=university,
        department=department,
        position=position,
        is_academician=is_academician,
        is_potential_recruit=is_potential_recruit,
        is_advisor_committee=is_advisor_committee,
        has_email=has_email,
        keyword=keyword,
    )

    filtered.sort(key=lambda i: i.get("name", ""))

    total = len(filtered)
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    start = (page - 1) * page_size
    page_items = filtered[start : start + page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": [_to_list_item(i) for i in page_items],
    }


def get_scholar_detail(url_hash: str) -> dict[str, Any] | None:
    """Return full scholar detail merged with annotations, or None if not found."""
    items = _load_all_with_annotations()
    for item in items:
        if item.get("url_hash", "") == url_hash:
            detail = _to_detail(item)
            detail["supervised_students_count"] = student_store.count_students(url_hash)
            return detail
    return None


def get_scholar_stats() -> dict[str, Any]:
    items = _load_all_with_annotations()

    total = len(items)
    academicians = sum(1 for i in items if i.get("is_academician", False))
    potential_recruits = sum(1 for i in items if i.get("is_potential_recruit", False))
    advisor_committee = sum(1 for i in items if i.get("is_advisor_committee", False))
    adjunct_supervisors = sum(
        1 for i in items
        if (i.get("adjunct_supervisor") or {}).get("status")
    )

    uni_counter: Counter = Counter()
    dept_counter: Counter = Counter()
    pos_counter: Counter = Counter()

    for item in items:
        uni = item.get("university", "") or "未知"
        uni_counter[uni] += 1
        dept = item.get("department", "") or "未知"
        dept_counter[(uni, dept)] += 1
        pos = item.get("position", "") or "未知"
        pos_counter[pos] += 1

    return {
        "total": total,
        "academicians": academicians,
        "potential_recruits": potential_recruits,
        "advisor_committee": advisor_committee,
        "adjunct_supervisors": adjunct_supervisors,
        "by_university": [
            {"university": u, "count": c}
            for u, c in uni_counter.most_common(15)
        ],
        "by_department": [
            {"university": u, "department": d, "count": c}
            for (u, d), c in dept_counter.most_common(30)
        ],
        "by_position": [
            {"position": p, "count": c}
            for p, c in pos_counter.most_common(10)
        ],
    }


# ---------------------------------------------------------------------------
# Write helpers (delegate to annotation_store)
# ---------------------------------------------------------------------------


def update_scholar_relation(url_hash: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    if get_scholar_detail(url_hash) is None:
        return None
    annotation_store.update_relation(url_hash, updates)
    return get_scholar_detail(url_hash)


def add_scholar_update(url_hash: str, update: dict[str, Any]) -> dict[str, Any] | None:
    if get_scholar_detail(url_hash) is None:
        return None
    annotation_store.add_user_update(url_hash, update)
    return get_scholar_detail(url_hash)


def delete_scholar_update(url_hash: str, update_idx: int) -> dict[str, Any] | None:
    if get_scholar_detail(url_hash) is None:
        return None
    annotation_store.delete_user_update(url_hash, update_idx)
    return get_scholar_detail(url_hash)


def update_scholar_achievements(url_hash: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    if get_scholar_detail(url_hash) is None:
        return None
    annotation_store.update_achievements(url_hash, updates)
    return get_scholar_detail(url_hash)


# ---------------------------------------------------------------------------
# Raw JSON modification helpers
# ---------------------------------------------------------------------------


def update_scholar_basic(url_hash: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update basic scholar information by modifying scholars.json directly.

    Returns the updated full detail (merged with annotations) or None if not found.
    """
    result = _find_raw_file_by_hash(url_hash)
    if result is None:
        return None

    file_path, item_idx = result

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    scholar = data["scholars"][item_idx]

    for key, value in updates.items():
        if key == "updated_by":
            continue
        if isinstance(value, list):
            scholar[key] = [
                v.model_dump() if hasattr(v, "model_dump") else v
                for v in value
            ]
        else:
            scholar[key] = value

    scholar["_user_modified_at"] = datetime.now(UTC).isoformat()
    scholar["_user_modified_by"] = updates.get("updated_by", "user")
    data["scholars"][item_idx] = scholar

    tmp_path = file_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(file_path)

    return get_scholar_detail(url_hash)


def delete_scholar(url_hash: str) -> bool:
    """Delete a scholar record from scholars.json."""
    try:
        result = _find_raw_file_by_hash(url_hash)
        if result is None:
            return False

        file_path, item_idx = result

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        scholars = data.get("scholars", [])
        if item_idx >= len(scholars) or scholars[item_idx].get("url_hash") != url_hash:
            return False

        scholars.pop(item_idx)
        data["scholars"] = scholars
        data["last_updated"] = datetime.now(UTC).isoformat()

        tmp_path = file_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(file_path)

        annotation_store.delete_all_for_faculty(url_hash)
        student_store.delete_all_students(url_hash)
        return True

    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(
            "Error deleting scholar %s: %s", url_hash, exc, exc_info=True
        )
        return False
