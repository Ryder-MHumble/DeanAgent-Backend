"""Backward-compatible facade — delegates to app.services.faculty subpackage.

All implementation now lives in app/services/faculty/:
  __init__.py      — public API
  _data.py         — raw JSON loading and annotation merging
  _filters.py      — filtering helpers
  _transformers.py — response shape converters
"""
from app.services.faculty import (  # noqa: F401
    add_faculty_update,
    delete_faculty_update,
    get_faculty_detail,
    get_faculty_list,
    get_faculty_sources,
    get_faculty_stats,
    update_faculty_achievements,
    update_faculty_basic,
    update_faculty_relation,
)
