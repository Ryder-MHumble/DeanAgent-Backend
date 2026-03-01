"""Faculty service — load, filter, and merge university_faculty data.

Data flow:
  1. Read all latest.json files under data/raw/university_faculty/
  2. Each item's `extra` field holds a ScholarRecord (model_dump())
  3. Load faculty_annotations.json and merge user-managed fields on top
  4. Apply filters and pagination
"""
from __future__ import annotations

import json
import logging
import math
from collections import Counter
from typing import Any

from app.crawlers.utils.json_storage import DATA_DIR, LATEST_FILENAME
from app.scheduler.manager import load_all_source_configs
from app.services import faculty_annotation_store as annotation_store
from app.services.intel.shared import parse_source_filter
from app.services.source_state import get_all_source_states

logger = logging.getLogger(__name__)

FACULTY_DIMENSION = "university_faculty"


# ---------------------------------------------------------------------------
# Raw data loading
# ---------------------------------------------------------------------------


def _iter_faculty_jsons():
    """Yield paths to all latest.json files under data/raw/university_faculty/."""
    raw_dir = DATA_DIR / FACULTY_DIMENSION
    if not raw_dir.exists():
        return
    for path in raw_dir.rglob(LATEST_FILENAME):
        yield path


def _load_all_raw() -> list[dict[str, Any]]:
    """Load all faculty items from raw JSON files.

    Returns a flat list of dicts, each being the CrawledItem dict with
    url_hash at the top level and ScholarRecord fields from extra merged in.
    """
    items: list[dict[str, Any]] = []
    for path in _iter_faculty_jsons():
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping invalid faculty JSON %s: %s", path, exc)
            continue

        group = payload.get("group", "")
        source_name = payload.get("source_name", "")
        for item in payload.get("items", []):
            url_hash = item.get("url_hash", "")
            if not url_hash:
                continue
            extra: dict[str, Any] = item.get("extra") or {}
            merged = {**extra}
            merged["url_hash"] = url_hash
            merged["group"] = extra.get("source_id", group).split("_")[
                0
            ] if not group else group
            merged["source_name"] = source_name
            items.append(merged)
    return items


# ---------------------------------------------------------------------------
# Annotation merging
# ---------------------------------------------------------------------------


_RELATION_FIELDS = [
    "is_advisor_committee",
    "is_adjunct_supervisor",
    "supervised_students",
    "joint_research_projects",
    "joint_management_roles",
    "academic_exchange_records",
    "is_potential_recruit",
    "institute_relation_notes",
    "relation_updated_by",
    "relation_updated_at",
]


def _merge_annotation(item: dict[str, Any], ann: dict[str, Any]) -> dict[str, Any]:
    """Overlay user annotation onto a faculty item (in-place, returns item)."""
    for field in _RELATION_FIELDS:
        if field in ann:
            item[field] = ann[field]

    user_updates = ann.get("user_updates", [])
    if user_updates:
        existing = list(item.get("recent_updates") or [])
        item["recent_updates"] = existing + user_updates
    return item


def _load_all_with_annotations() -> list[dict[str, Any]]:
    """Load raw faculty data and merge user annotations."""
    items = _load_all_raw()
    if not items:
        return items

    # Load all annotations in one pass
    all_annotations = annotation_store._load()  # internal helper, single read
    if not all_annotations:
        return items

    for item in items:
        url_hash = item.get("url_hash", "")
        if url_hash in all_annotations:
            _merge_annotation(item, all_annotations[url_hash])
    return items


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------


def _match_fuzzy(value: str, query: str) -> bool:
    return query.strip().lower() in (value or "").lower()


def _apply_filters(
    items: list[dict[str, Any]],
    *,
    university: str | None,
    department: str | None,
    group: str | None,
    position: str | None,
    is_academician: bool | None,
    is_potential_recruit: bool | None,
    is_advisor_committee: bool | None,
    has_email: bool | None,
    min_completeness: int | None,
    keyword: str | None,
    source_filter: set[str] | None,
) -> list[dict[str, Any]]:
    result = items

    if source_filter is not None:
        result = [i for i in result if i.get("source_id", "") in source_filter]

    if group:
        result = [i for i in result if i.get("group", "") == group]

    if university:
        result = [i for i in result if _match_fuzzy(i.get("university", ""), university)]

    if department:
        result = [i for i in result if _match_fuzzy(i.get("department", ""), department)]

    if position:
        result = [i for i in result if i.get("position", "") == position]

    if is_academician is not None:
        result = [i for i in result if bool(i.get("is_academician", False)) == is_academician]

    if is_potential_recruit is not None:
        result = [
            i for i in result
            if bool(i.get("is_potential_recruit", False)) == is_potential_recruit
        ]

    if is_advisor_committee is not None:
        result = [
            i for i in result
            if bool(i.get("is_advisor_committee", False)) == is_advisor_committee
        ]

    if has_email is not None:
        result = [i for i in result if bool(i.get("email", "")) == has_email]

    if min_completeness is not None:
        result = [i for i in result if (i.get("data_completeness") or 0) >= min_completeness]

    if keyword:
        kw = keyword.strip().lower()
        def _matches(i: dict[str, Any]) -> bool:
            if kw in (i.get("name") or "").lower():
                return True
            if kw in (i.get("name_en") or "").lower():
                return True
            if kw in (i.get("bio") or "").lower():
                return True
            if any(kw in area.lower() for area in (i.get("research_areas") or [])):
                return True
            if any(kw in kw_tag.lower() for kw_tag in (i.get("keywords") or [])):
                return True
            return False

        result = [i for i in result if _matches(i)]

    return result


# ---------------------------------------------------------------------------
# Item transformers
# ---------------------------------------------------------------------------


def _to_list_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "url_hash": item.get("url_hash", ""),
        "name": item.get("name", ""),
        "name_en": item.get("name_en", ""),
        "photo_url": item.get("photo_url", ""),
        "university": item.get("university", ""),
        "department": item.get("department", ""),
        "position": item.get("position", ""),
        "academic_titles": item.get("academic_titles") or [],
        "is_academician": bool(item.get("is_academician", False)),
        "research_areas": item.get("research_areas") or [],
        "email": item.get("email", ""),
        "profile_url": item.get("profile_url", ""),
        "source_id": item.get("source_id", ""),
        "group": item.get("group", ""),
        "data_completeness": item.get("data_completeness") or 0,
        "is_potential_recruit": bool(item.get("is_potential_recruit", False)),
        "is_advisor_committee": bool(item.get("is_advisor_committee", False)),
        "is_adjunct_supervisor": bool(item.get("is_adjunct_supervisor", False)),
        "crawled_at": item.get("crawled_at", ""),
    }


def _to_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "url_hash": item.get("url_hash", ""),
        "source_id": item.get("source_id", ""),
        "group": item.get("group", ""),
        "name": item.get("name", ""),
        "name_en": item.get("name_en", ""),
        "gender": item.get("gender", ""),
        "photo_url": item.get("photo_url", ""),
        "university": item.get("university", ""),
        "department": item.get("department", ""),
        "secondary_departments": item.get("secondary_departments") or [],
        "position": item.get("position", ""),
        "academic_titles": item.get("academic_titles") or [],
        "is_academician": bool(item.get("is_academician", False)),
        "research_areas": item.get("research_areas") or [],
        "keywords": item.get("keywords") or [],
        "bio": item.get("bio", ""),
        "bio_en": item.get("bio_en", ""),
        "email": item.get("email", ""),
        "phone": item.get("phone", ""),
        "office": item.get("office", ""),
        "profile_url": item.get("profile_url", ""),
        "lab_url": item.get("lab_url", ""),
        "google_scholar_url": item.get("google_scholar_url", ""),
        "dblp_url": item.get("dblp_url", ""),
        "orcid": item.get("orcid", ""),
        "phd_institution": item.get("phd_institution", ""),
        "phd_year": item.get("phd_year", ""),
        "education": item.get("education") or [],
        "publications_count": item.get("publications_count", -1),
        "h_index": item.get("h_index", -1),
        "citations_count": item.get("citations_count", -1),
        "metrics_updated_at": item.get("metrics_updated_at", ""),
        "is_advisor_committee": bool(item.get("is_advisor_committee", False)),
        "is_adjunct_supervisor": bool(item.get("is_adjunct_supervisor", False)),
        "supervised_students": item.get("supervised_students") or [],
        "joint_research_projects": item.get("joint_research_projects") or [],
        "joint_management_roles": item.get("joint_management_roles") or [],
        "academic_exchange_records": item.get("academic_exchange_records") or [],
        "is_potential_recruit": bool(item.get("is_potential_recruit", False)),
        "institute_relation_notes": item.get("institute_relation_notes", ""),
        "relation_updated_by": item.get("relation_updated_by", ""),
        "relation_updated_at": item.get("relation_updated_at", ""),
        "recent_updates": item.get("recent_updates") or [],
        "source_url": item.get("source_url", ""),
        "crawled_at": item.get("crawled_at", ""),
        "first_seen_at": item.get("first_seen_at", ""),
        "last_seen_at": item.get("last_seen_at", ""),
        "is_active": bool(item.get("is_active", True)),
        "data_completeness": item.get("data_completeness") or 0,
    }


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def get_faculty_list(
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


def get_faculty_detail(url_hash: str) -> dict[str, Any] | None:
    """Return full faculty detail merged with annotations, or None if not found."""
    items = _load_all_with_annotations()
    for item in items:
        if item.get("url_hash", "") == url_hash:
            return _to_detail(item)
    return None


def get_faculty_stats() -> dict[str, Any]:
    items = _load_all_with_annotations()

    total = len(items)
    academicians = sum(1 for i in items if i.get("is_academician", False))
    potential_recruits = sum(1 for i in items if i.get("is_potential_recruit", False))
    advisor_committee = sum(1 for i in items if i.get("is_advisor_committee", False))
    adjunct_supervisors = sum(1 for i in items if i.get("is_adjunct_supervisor", False))

    uni_counter: Counter = Counter()
    pos_counter: Counter = Counter()
    completeness_buckets = {"<30": 0, "30-60": 0, "60-80": 0, ">80": 0}

    for item in items:
        uni = item.get("university", "") or "未知"
        uni_counter[uni] += 1

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
    by_position = [
        {"position": p, "count": c}
        for p, c in pos_counter.most_common(10)
    ]

    # Count faculty sources
    configs = load_all_source_configs()
    sources_count = sum(1 for c in configs if c.get("dimension") == FACULTY_DIMENSION)

    return {
        "total": total,
        "academicians": academicians,
        "potential_recruits": potential_recruits,
        "advisor_committee": advisor_committee,
        "adjunct_supervisors": adjunct_supervisors,
        "by_university": by_university,
        "by_position": by_position,
        "completeness_buckets": completeness_buckets,
        "sources_count": sources_count,
    }


def get_faculty_sources() -> dict[str, Any]:
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


def update_faculty_relation(url_hash: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update institute relation fields. Returns merged detail or None if faculty not found."""
    # Verify faculty exists
    detail = get_faculty_detail(url_hash)
    if detail is None:
        return None
    annotation_store.update_relation(url_hash, updates)
    return get_faculty_detail(url_hash)


def add_faculty_update(url_hash: str, update: dict[str, Any]) -> dict[str, Any] | None:
    """Add a user-authored dynamic update. Returns merged detail or None if not found."""
    detail = get_faculty_detail(url_hash)
    if detail is None:
        return None
    annotation_store.add_user_update(url_hash, update)
    return get_faculty_detail(url_hash)


def delete_faculty_update(
    url_hash: str, update_idx: int
) -> dict[str, Any] | None:
    """Delete a user dynamic update. Returns merged detail or None if not found.

    Raises ValueError if index out of range; PermissionError if targeting crawler entry.
    """
    detail = get_faculty_detail(url_hash)
    if detail is None:
        return None
    annotation_store.delete_user_update(url_hash, update_idx)
    return get_faculty_detail(url_hash)
