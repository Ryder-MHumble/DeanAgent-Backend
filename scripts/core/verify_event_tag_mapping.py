#!/usr/bin/env python3
"""Verify event tag-model field mapping consistency.

Checks:
- DB row -> API detail uses `poster_url -> cover_image_url`
- DB row -> API detail uses `description -> abstract`
- API payload -> DB row uses `cover_image_url -> poster_url`
- API payload -> DB row uses `abstract -> description`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.core.event_service import _db_to_detail, _event_to_db_row


def main() -> int:
    row = {
        "id": "e1",
        "category": "科研学术",
        "series": "XAI智汇讲坛",
        "event_type": "学术年会",
        "title": "活动标题",
        "description": "活动摘要",
        "event_date": "2026-03-26",
        "event_time": "14:00-16:00",
        "location": "C8",
        "poster_url": "https://example.com/cover.png",
        "scholar_ids": ["s1", "s2"],
    }
    detail = _db_to_detail(row)
    assert detail.cover_image_url == "https://example.com/cover.png"
    assert detail.abstract == "活动摘要"
    assert detail.scholar_ids == ["s1", "s2"]

    db_row = _event_to_db_row(
        {
            "id": "e1",
            "category": "科研学术",
            "series": "XAI智汇讲坛",
            "event_type": "学术年会",
            "title": "活动标题",
            "abstract": "活动摘要",
            "event_date": "2026-03-26",
            "event_time": "14:00-16:00",
            "location": "C8",
            "cover_image_url": "https://example.com/cover.png",
            "scholar_ids": ["s1", "s2"],
        }
    )
    assert db_row["description"] == "活动摘要"
    assert db_row["poster_url"] == "https://example.com/cover.png"

    print("PASS: event tag mapping")
    print(
        json.dumps(
            {
                "detail_cover_image_url": detail.cover_image_url,
                "detail_abstract": detail.abstract,
                "db_description": db_row["description"],
                "db_poster_url": db_row["poster_url"],
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
        print(f"FAIL: event mapping assertion failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
