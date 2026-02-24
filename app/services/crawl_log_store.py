"""Append-only crawl log storage in local JSON files.

Each source gets its own log file: data/logs/{source_id}/crawl_logs.json
The file contains a JSON array of log entries, capped at MAX_LOGS_PER_SOURCE.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import BASE_DIR

logger = logging.getLogger(__name__)

LOGS_DIR = BASE_DIR / "data" / "logs"
MAX_LOGS_PER_SOURCE = 100


def _log_file(source_id: str) -> Path:
    return LOGS_DIR / source_id / "crawl_logs.json"


def _load_logs(source_id: str) -> list[dict[str, Any]]:
    path = _log_file(source_id)
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_logs(source_id: str, logs: list[dict[str, Any]]) -> None:
    path = _log_file(source_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2, default=str)


def append_crawl_log(
    source_id: str,
    *,
    status: str,
    items_total: int = 0,
    items_new: int = 0,
    error_message: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    duration_seconds: float = 0.0,
) -> None:
    logs = _load_logs(source_id)

    entry = {
        "source_id": source_id,
        "status": status,
        "items_total": items_total,
        "items_new": items_new,
        "error_message": error_message,
        "started_at": started_at.isoformat() if started_at else None,
        "finished_at": finished_at.isoformat() if finished_at else None,
        "duration_seconds": duration_seconds,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    logs.append(entry)

    if len(logs) > MAX_LOGS_PER_SOURCE:
        logs = logs[-MAX_LOGS_PER_SOURCE:]

    _save_logs(source_id, logs)


def get_crawl_logs(
    source_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if source_id:
        logs = _load_logs(source_id)
        logs.sort(key=lambda x: x.get("started_at") or "", reverse=True)
        return logs[:limit]

    # All sources: scan all log files
    all_logs: list[dict[str, Any]] = []
    if LOGS_DIR.exists():
        for source_dir in LOGS_DIR.iterdir():
            if source_dir.is_dir():
                all_logs.extend(_load_logs(source_dir.name))

    all_logs.sort(key=lambda x: x.get("started_at") or "", reverse=True)
    return all_logs[:limit]


def get_recent_log_stats(hours: int = 24) -> dict[str, int]:
    """Get crawl and article counts from the last N hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    total_crawls = 0
    total_new_articles = 0

    if not LOGS_DIR.exists():
        return {"crawls": 0, "new_articles": 0}

    for source_dir in LOGS_DIR.iterdir():
        if not source_dir.is_dir():
            continue
        for log in _load_logs(source_dir.name):
            started = log.get("started_at") or ""
            if started >= cutoff:
                total_crawls += 1
                total_new_articles += log.get("items_new", 0)

    return {"crawls": total_crawls, "new_articles": total_new_articles}
