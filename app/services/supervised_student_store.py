"""Thread-safe store for supervised student records.

Each faculty member (identified by url_hash) can have a list of students.
Storage: data/state/supervised_students.json

Format:
{
  "{faculty_url_hash}": [
    {
      "id": "uuid4-string",
      "student_no": "240101003",
      "name": "何雨桐",
      "home_university": "北京大学",
      "degree_type": "博士",
      "enrollment_year": "2024",
      "expected_graduation_year": "2027",
      "status": "在读",
      "email": "",
      "phone": "",
      "notes": "",
      "added_by": "user:admin",
      "created_at": "2026-03-02T10:00:00+00:00",
      "updated_at": "2026-03-02T10:00:00+00:00"
    }
  ]
}
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

from app.config import BASE_DIR

logger = logging.getLogger(__name__)

STUDENTS_FILE = BASE_DIR / "data" / "state" / "supervised_students.json"
_lock = Lock()

# ---------------------------------------------------------------------------
# Internal I/O helpers
# ---------------------------------------------------------------------------


def _load() -> dict[str, list[dict[str, Any]]]:
    if not STUDENTS_FILE.exists():
        return {}
    try:
        with open(STUDENTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict[str, list[dict[str, Any]]]) -> None:
    STUDENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STUDENTS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(STUDENTS_FILE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_students(faculty_url_hash: str) -> list[dict[str, Any]]:
    """Return all student records for a faculty member, or [] if none."""
    with _lock:
        data = _load()
    return data.get(faculty_url_hash, [])


def get_student(faculty_url_hash: str, student_id: str) -> dict[str, Any] | None:
    """Return a single student record by id, or None if not found."""
    with _lock:
        data = _load()
    students = data.get(faculty_url_hash, [])
    for student in students:
        if student.get("id") == student_id:
            return student
    return None


def add_student(faculty_url_hash: str, data_in: dict[str, Any]) -> dict[str, Any]:
    """Append a new student record and return it.

    Generates server-side id, created_at, updated_at.
    Normalises added_by to 'user:{username}'.
    """
    now = datetime.now(timezone.utc).isoformat()
    raw_added_by = data_in.get("added_by", "")
    record: dict[str, Any] = {
        "id": str(uuid4()),
        "student_no": data_in.get("student_no", ""),
        "name": data_in.get("name", ""),
        "home_university": data_in.get("home_university", ""),
        "degree_type": data_in.get("degree_type", ""),
        "enrollment_year": data_in.get("enrollment_year", ""),
        "expected_graduation_year": data_in.get("expected_graduation_year", ""),
        "status": data_in.get("status", "在读"),
        "email": data_in.get("email", ""),
        "phone": data_in.get("phone", ""),
        "notes": data_in.get("notes", ""),
        "added_by": f"user:{raw_added_by}" if raw_added_by else "user:unknown",
        "created_at": now,
        "updated_at": now,
    }
    with _lock:
        data = _load()
        data.setdefault(faculty_url_hash, []).append(record)
        _save(data)
    return record


def update_student(
    faculty_url_hash: str,
    student_id: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    """Apply partial updates to a student record.

    Returns the updated record, or None if not found.
    Only whitelisted mutable fields are applied; 'updated_at' is auto-set.
    """
    _MUTABLE_FIELDS = {
        "student_no",
        "name",
        "home_university",
        "degree_type",
        "enrollment_year",
        "expected_graduation_year",
        "status",
        "email",
        "phone",
        "notes",
    }
    with _lock:
        data = _load()
        students = data.get(faculty_url_hash, [])
        for student in students:
            if student.get("id") == student_id:
                for key, val in updates.items():
                    if key in _MUTABLE_FIELDS and val is not None:
                        student[key] = val
                student["updated_at"] = datetime.now(timezone.utc).isoformat()
                _save(data)
                return student
    return None


def delete_student(faculty_url_hash: str, student_id: str) -> bool:
    """Delete a student record by id. Returns True if deleted, False if not found."""
    with _lock:
        data = _load()
        students = data.get(faculty_url_hash, [])
        new_list = [s for s in students if s.get("id") != student_id]
        if len(new_list) == len(students):
            return False
        data[faculty_url_hash] = new_list
        _save(data)
    return True


def count_students(faculty_url_hash: str) -> int:
    """Return the number of students for a faculty member."""
    with _lock:
        data = _load()
    return len(data.get(faculty_url_hash, []))
