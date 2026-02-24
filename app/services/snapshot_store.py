"""Local JSON storage for page snapshots (used by SnapshotDiffCrawler).

Replaces the 'snapshots' DB table. Each source gets one file:
  data/state/snapshots/{source_id}.json
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.config import BASE_DIR

SNAPSHOTS_DIR = BASE_DIR / "data" / "state" / "snapshots"


def get_last_snapshot(source_id: str) -> dict[str, Any] | None:
    path = SNAPSHOTS_DIR / f"{source_id}.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_snapshot(
    source_id: str,
    content_hash: str,
    content_text: str,
    diff_text: str | None = None,
) -> None:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "source_id": source_id,
        "content_hash": content_hash,
        "content_text": content_text,
        "diff_text": diff_text,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    path = SNAPSHOTS_DIR / f"{source_id}.json"
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)
