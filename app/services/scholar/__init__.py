"""Faculty service — public API for loading, filtering, and updating faculty data.

Internal implementation is split across private sub-modules:
  _data.py         — raw JSON loading and annotation merging
  _filters.py      — multi-field filtering helpers
  _transformers.py — response shape converters (_to_list_item, _to_detail)
"""
from __future__ import annotations

import json
import math
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from app.scheduler.manager import load_all_source_configs
from app.services import scholar_annotation_store as annotation_store
from app.services import supervised_student_store as student_store
from app.services.faculty._data import (
    FACULTY_DIMENSION,
    _find_raw_file_by_hash,
    _iter_faculty_jsons,
    _load_all_with_annotations,
)
from app.services.faculty._filters import _apply_filters
from app.services.faculty._transformers import _to_detail, _to_list_item
from app.services.intel.source_filter import parse_source_filter
from app.services.source_state import get_all_source_states

# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------


def get_scholar_list(
    *,
    university: str | None = None,
    department: str | None = None,
    group: str | None = None,
    position: str | None = None,
    is_academician: bool | None = None,
    is_potential_recruit: bool | None = None,
    is_advisor_committee: bool | None = None,
    has_email: bool | None = None,
    min_completeness: int | None = None,
    keyword: str | None = None,
    source_id: str | None = None,
    source_ids: str | None = None,
    source_name: str | None = None,
    source_names: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    items = _load_all_with_annotations()

    source_filter = parse_source_filter(source_id, source_ids, source_name, source_names)

    filtered = _apply_filters(
        items,
        university=university,
        department=department,
        group=group,
        position=position,
        is_academician=is_academician,
        is_potential_recruit=is_potential_recruit,
        is_advisor_committee=is_advisor_committee,
        has_email=has_email,
        min_completeness=min_completeness,
        keyword=keyword,
        source_filter=source_filter,
    )

    # Sort: by name for stable ordering
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
    """Return full faculty detail merged with annotations, or None if not found."""
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
    adjunct_supervisors = sum(1 for i in items if i.get("is_adjunct_supervisor", False))

    uni_counter: Counter = Counter()
    dept_counter: Counter = Counter()
    pos_counter: Counter = Counter()
    completeness_buckets = {"<30": 0, "30-60": 0, "60-80": 0, ">80": 0}

    for item in items:
        uni = item.get("university", "") or "未知"
        uni_counter[uni] += 1

        dept = item.get("department", "") or "未知"
        dept_key = (uni, dept)
        dept_counter[dept_key] += 1

        pos = item.get("position", "") or "未知"
        pos_counter[pos] += 1

        score = item.get("data_completeness") or 0
        if score < 30:
            completeness_buckets["<30"] += 1
        elif score < 60:
            completeness_buckets["30-60"] += 1
        elif score < 80:
            completeness_buckets["60-80"] += 1
        else:
            completeness_buckets[">80"] += 1

    by_university = [
        {"university": u, "count": c}
        for u, c in uni_counter.most_common(15)
    ]
    by_department = [
        {"university": u, "department": d, "count": c}
        for (u, d), c in dept_counter.most_common(30)
    ]
    by_position = [
        {"position": p, "count": c}
        for p, c in pos_counter.most_common(10)
    ]

    configs = load_all_source_configs()
    sources_count = sum(1 for c in configs if c.get("dimension") == FACULTY_DIMENSION)

    return {
        "total": total,
        "academicians": academicians,
        "potential_recruits": potential_recruits,
        "advisor_committee": advisor_committee,
        "adjunct_supervisors": adjunct_supervisors,
        "by_university": by_university,
        "by_department": by_department,
        "by_position": by_position,
        "completeness_buckets": completeness_buckets,
        "sources_count": sources_count,
    }


def get_scholar_sources() -> dict[str, Any]:
    """Return list of university_faculty sources with crawl status and item count."""
    configs = load_all_source_configs()
    states = get_all_source_states()

    faculty_configs = [c for c in configs if c.get("dimension") == FACULTY_DIMENSION]

    # Count items per source from raw files
    item_counts: dict[str, int] = {}
    for path in _iter_faculty_jsons():
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
            sid = payload.get("source_id", path.parent.name)
            item_counts[sid] = payload.get("item_count", len(payload.get("items", [])))
        except (json.JSONDecodeError, OSError):
            pass

    items = []
    for cfg in faculty_configs:
        sid = cfg.get("id", "")
        state = states.get(sid, {})
        override = state.get("is_enabled_override")
        is_enabled = override if override is not None else cfg.get("is_enabled", True)

        items.append({
            "id": sid,
            "name": cfg.get("name", sid),
            "group": cfg.get("group", ""),
            "university": cfg.get("university", ""),
            "department": cfg.get("department", ""),
            "is_enabled": is_enabled,
            "item_count": item_counts.get(sid, 0),
            "last_crawl_at": state.get("last_crawl_at"),
        })

    items.sort(key=lambda s: (s["university"], s["name"]))

    return {"total": len(items), "items": items}


# ---------------------------------------------------------------------------
# Write helpers (delegate to annotation_store)
# ---------------------------------------------------------------------------


def update_scholar_relation(url_hash: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update institute relation fields. Returns merged detail or None if faculty not found."""
    if get_scholar_detail(url_hash) is None:
        return None
    annotation_store.update_relation(url_hash, updates)
    return get_scholar_detail(url_hash)


def add_scholar_update(url_hash: str, update: dict[str, Any]) -> dict[str, Any] | None:
    """Add a user-authored dynamic update. Returns merged detail or None if not found."""
    if get_scholar_detail(url_hash) is None:
        return None
    annotation_store.add_user_update(url_hash, update)
    return get_scholar_detail(url_hash)


def delete_scholar_update(url_hash: str, update_idx: int) -> dict[str, Any] | None:
    """Delete a user dynamic update. Returns merged detail or None if not found.

    Raises ValueError if index out of range; PermissionError if targeting crawler entry.
    """
    if get_scholar_detail(url_hash) is None:
        return None
    annotation_store.delete_user_update(url_hash, update_idx)
    return get_scholar_detail(url_hash)


def update_scholar_achievements(url_hash: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update academic achievement fields. Returns merged detail or None if faculty not found."""
    if get_scholar_detail(url_hash) is None:
        return None
    annotation_store.update_achievements(url_hash, updates)
    return get_scholar_detail(url_hash)


# ---------------------------------------------------------------------------
# Raw JSON modification helpers
# ---------------------------------------------------------------------------


def update_scholar_basic(url_hash: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update basic faculty information by modifying raw JSON file directly.

    Locates the faculty record by url_hash, applies field updates to the
    'extra' (ScholarRecord) section, and writes back atomically.

    Returns the updated full detail (merged with annotations) or None if not found.
    """
    result = _find_raw_file_by_hash(url_hash)
    if result is None:
        return None

    file_path, item_idx = result

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    item = data["items"][item_idx]
    scholar = item.get("extra") or {}

    update_dict = {k: v for k, v in updates.items() if v is not None}
    for key, value in update_dict.items():
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

    item["extra"] = scholar
    data["items"][item_idx] = item

    # Atomic write: write to temp file, then replace
    tmp_path = file_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(file_path)

    return get_scholar_detail(url_hash)


def delete_scholar(url_hash: str) -> bool:
    """Delete a faculty record by removing it from the raw JSON file.

    Returns True if deleted successfully, False if not found.
    Includes clean-up of related data (annotations, supervised students).

    Thread-safe: handles concurrent delete requests gracefully.
    """
    try:
        result = _find_raw_file_by_hash(url_hash)
        if result is None:
            return False

        file_path, item_idx = result

        # Read file once
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        # Verify the item still exists at this index (handles concurrent deletes)
        if item_idx >= len(data.get("items", [])):
            return False

        if data["items"][item_idx].get("url_hash") != url_hash:
            # Index mismatch - re-search to find correct index (race condition check)
            for idx, item in enumerate(data.get("items", [])):
                if item.get("url_hash") == url_hash:
                    item_idx = idx
                    break
            else:
                return False

        # Remove the item from the items array
        data["items"].pop(item_idx)

        # Update item_count
        data["item_count"] = len(data["items"])

        # Atomic write: write to temp file, then replace
        tmp_path = file_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(file_path)

        # Clean up related data (annotations and supervised students)
        annotation_store.delete_all_for_faculty(url_hash)
        student_store.delete_all_students(url_hash)

        return True
    except Exception as exc:
        # Log the exception and return False to prevent 500 errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error("Error deleting faculty %s: %s", url_hash, exc, exc_info=True)
        return False
