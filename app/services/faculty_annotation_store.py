"""Thread-safe store for user-managed faculty annotations.

Annotations overlay crawled ScholarRecord data without modifying the raw JSON files.
Storage: data/state/faculty_annotations.json

Format:
{
  "{url_hash}": {
    "is_advisor_committee": bool,
    "is_adjunct_supervisor": bool,
    "supervised_students": list[str],
    "joint_research_projects": list[str],
    "joint_management_roles": list[str],
    "academic_exchange_records": list[str],
    "is_potential_recruit": bool,
    "institute_relation_notes": str,
    "relation_updated_by": str,
    "relation_updated_at": str,   // ISO8601
    "user_updates": [
      { update_type, title, content, source_url, published_at, added_by, created_at }
    ]
  }
}
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from app.config import BASE_DIR

logger = logging.getLogger(__name__)

ANNOTATIONS_FILE = BASE_DIR / "data" / "state" / "faculty_annotations.json"
_lock = Lock()

# ---------------------------------------------------------------------------
# Internal I/O helpers
# ---------------------------------------------------------------------------


def _load() -> dict[str, dict[str, Any]]:
    if not ANNOTATIONS_FILE.exists():
        return {}
    try:
        with open(ANNOTATIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict[str, dict[str, Any]]) -> None:
    ANNOTATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = ANNOTATIONS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(ANNOTATIONS_FILE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_annotation(url_hash: str) -> dict[str, Any]:
    """Return the annotation dict for a faculty member, or {} if none exists."""
    with _lock:
        data = _load()
    return data.get(url_hash, {})


def update_relation(url_hash: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Merge *updates* into the institute-relation section of the annotation.

    Auto-sets relation_updated_at to current UTC time.
    Returns the updated annotation dict.
    """
    with _lock:
        data = _load()
        ann = data.setdefault(url_hash, {})

        _RELATION_FIELDS = {
            "is_advisor_committee",
            "is_adjunct_supervisor",
            "supervised_students",
            "joint_research_projects",
            "joint_management_roles",
            "academic_exchange_records",
            "is_potential_recruit",
            "institute_relation_notes",
            "relation_updated_by",
        }
        for key, val in updates.items():
            if key in _RELATION_FIELDS and val is not None:
                ann[key] = val

        ann["relation_updated_at"] = datetime.now(timezone.utc).isoformat()
        _save(data)
    return ann


def add_user_update(url_hash: str, update: dict[str, Any]) -> dict[str, Any]:
    """Append a user-authored dynamic update entry.

    Returns the updated annotation dict.
    """
    with _lock:
        data = _load()
        ann = data.setdefault(url_hash, {})
        user_updates = ann.setdefault("user_updates", [])
        entry = {
            "update_type": update.get("update_type", "other"),
            "title": update.get("title", ""),
            "content": update.get("content", ""),
            "source_url": update.get("source_url", ""),
            "published_at": update.get("published_at", ""),
            "added_by": f"user:{update.get('added_by', 'unknown')}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        user_updates.append(entry)
        _save(data)
    return ann


def delete_user_update(url_hash: str, update_idx: int) -> dict[str, Any] | None:
    """Delete a user-authored dynamic update by index in the merged recent_updates list.

    *update_idx* refers to the index in the combined recent_updates list
    (crawler items first, user_updates appended after).  We identify user entries
    by their ``added_by`` prefix 'user:'.

    Returns:
        Updated annotation dict, or None if url_hash not found.
    Raises:
        ValueError if index is out of range or points to a crawler entry.
    """
    with _lock:
        data = _load()
        if url_hash not in data:
            return None

        ann = data[url_hash]
        user_updates = ann.get("user_updates", [])

        # The merged list order is: crawler recent_updates (unknown count) then user_updates.
        # We only store user_updates in annotations; the idx into user_updates list is needed.
        # We accept update_idx as index into user_updates directly (0-based).
        if update_idx < 0 or update_idx >= len(user_updates):
            raise ValueError(
                f"Index {update_idx} out of range (user_updates has {len(user_updates)} entries)"
            )

        entry = user_updates[update_idx]
        if not entry.get("added_by", "").startswith("user:"):
            raise PermissionError("Cannot delete crawler-generated dynamic updates")

        user_updates.pop(update_idx)
        ann["user_updates"] = user_updates
        _save(data)
    return ann
