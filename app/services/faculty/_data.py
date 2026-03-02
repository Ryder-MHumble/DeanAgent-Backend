"""Raw data loading and annotation merging for faculty service."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.crawlers.utils.json_storage import DATA_DIR, LATEST_FILENAME
from app.services import faculty_annotation_store as annotation_store

logger = logging.getLogger(__name__)

FACULTY_DIMENSION = "university_faculty"

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

_ACHIEVEMENT_FIELDS = [
    "representative_publications",
    "patents",
    "awards",
]


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
            merged["group"] = (
                extra.get("source_id", group).split("_")[0] if not group else group
            )
            merged["source_name"] = source_name
            items.append(merged)
    return items


def _merge_annotation(item: dict[str, Any], ann: dict[str, Any]) -> dict[str, Any]:
    """Overlay user annotation onto a faculty item (in-place, returns item)."""
    for field in _RELATION_FIELDS:
        if field in ann:
            item[field] = ann[field]

    # Achievement fields: user annotation completely replaces crawler data
    for field in _ACHIEVEMENT_FIELDS:
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


def _find_raw_file_by_hash(url_hash: str) -> tuple[Path, int] | None:
    """Locate the raw JSON file and item index for a given url_hash.

    Returns (file_path, item_index) or None if not found.
    """
    for path in _iter_faculty_jsons():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        items = data.get("items", [])
        for idx, item in enumerate(items):
            if item.get("url_hash") == url_hash:
                return path, idx
    return None
