#!/usr/bin/env python3
"""Verify project tag-model compatibility mapping.

Checks legacy-compatible extraction behavior in project service:
- subcategory extraction from legacy tags
- scholar_ids extraction from related_scholars
- detail mapping to tag-model response fields
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.core.project_service import (
    _extract_scholar_ids,
    _extract_subcategory,
    _to_detail,
)


def main() -> int:
    row = {
        "id": "p1",
        "name": "教育培养-学术委员会",
        "description": "说明",
        "category": "教育培养",
        "tags": ["教育培养", "教育培养-学术委员会"],
        "related_scholars": [
            {"scholar_id": "s1"},
            {"id": "s2"},
            {"url_hash": "s3"},
        ],
        "custom_fields": {},
    }

    subcategory = _extract_subcategory(row)
    scholar_ids = _extract_scholar_ids(row)
    detail = _to_detail(row)

    assert subcategory == "学术委员会"
    assert scholar_ids == ["s1", "s2", "s3"]
    assert detail.category == "教育培养"
    assert detail.subcategory == "学术委员会"
    assert detail.title == "教育培养-学术委员会"
    assert detail.summary == "说明"
    assert detail.scholar_ids == ["s1", "s2", "s3"]

    print("PASS: project tag mapping")
    print(
        json.dumps(
            {
                "subcategory": subcategory,
                "scholar_ids": scholar_ids,
                "detail": detail.model_dump(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: project mapping assertion failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
