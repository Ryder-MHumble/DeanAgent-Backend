"""Cross-process crawl runtime state store for console sync."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import BASE_DIR

STATE_DIR = BASE_DIR / "data" / "state"
RUNTIME_FILE = STATE_DIR / "crawl_runtime.json"

_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _load_raw() -> dict[str, Any]:
    if not RUNTIME_FILE.exists():
        return {}
    try:
        with open(RUNTIME_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        return {}
    return {}


def _save_raw(payload: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(f"{RUNTIME_FILE}.tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    tmp.replace(RUNTIME_FILE)


def get_crawl_runtime_state() -> dict[str, Any]:
    """Return latest runtime state, always with stable keys."""
    with _LOCK:
        payload = _load_raw()

    return {
        "is_running": bool(payload.get("is_running", False)),
        "mode": str(payload.get("mode") or "manual"),
        "current_source": payload.get("current_source"),
        "requested_source_count": int(payload.get("requested_source_count") or 0),
        "completed_count": int(payload.get("completed_count") or 0),
        "failed_count": int(payload.get("failed_count") or 0),
        "completed_sources": list(payload.get("completed_sources") or []),
        "failed_sources": list(payload.get("failed_sources") or []),
        "total_items": int(payload.get("total_items") or 0),
        "progress": float(payload.get("progress") or 0.0),
        "started_at": payload.get("started_at"),
        "finished_at": payload.get("finished_at"),
        "result_file_name": payload.get("result_file_name"),
        "updated_at": payload.get("updated_at"),
    }


def set_crawl_runtime_state(**updates: Any) -> dict[str, Any]:
    """Merge updates into runtime state and persist atomically."""
    with _LOCK:
        payload = _load_raw()
        payload.update(updates)
        payload["updated_at"] = _now_iso()
        _save_raw(payload)
        return dict(payload)
