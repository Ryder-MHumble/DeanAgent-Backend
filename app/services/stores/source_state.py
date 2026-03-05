"""Manage mutable source runtime state in a local JSON file.

The YAML configs provide static configuration (url, schedule, selectors, etc.).
This module manages the dynamic runtime state that changes with each crawl:
  - last_crawl_at
  - last_success_at
  - consecutive_failures
  - is_enabled_override (API toggle, overrides YAML is_enabled)

State file: data/state/source_state.json
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from threading import Lock
from typing import Any

from app.config import BASE_DIR

logger = logging.getLogger(__name__)

STATE_DIR = BASE_DIR / "data" / "state"
STATE_FILE = STATE_DIR / "source_state.json"

_lock = Lock()


def _load_state() -> dict[str, dict[str, Any]]:
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupted source_state.json, starting fresh")
        return {}


def _save_state(state: dict[str, dict[str, Any]]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)
    tmp.replace(STATE_FILE)


def get_source_state(source_id: str) -> dict[str, Any]:
    return _load_state().get(source_id, {})


def get_all_source_states() -> dict[str, dict[str, Any]]:
    return _load_state()


def update_source_state(
    source_id: str,
    *,
    last_crawl_at: datetime | None = None,
    last_success_at: datetime | None = None,
    consecutive_failures: int | None = None,
    reset_failures: bool = False,
) -> None:
    with _lock:
        state = _load_state()
        entry = state.setdefault(source_id, {})
        if last_crawl_at:
            entry["last_crawl_at"] = last_crawl_at.isoformat()
        if last_success_at:
            entry["last_success_at"] = last_success_at.isoformat()
        if reset_failures:
            entry["consecutive_failures"] = 0
        elif consecutive_failures is not None:
            entry["consecutive_failures"] = consecutive_failures
        else:
            entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
        _save_state(state)


def set_enabled_override(source_id: str, is_enabled: bool) -> None:
    with _lock:
        state = _load_state()
        entry = state.setdefault(source_id, {})
        entry["is_enabled_override"] = is_enabled
        _save_state(state)


def get_enabled_override(source_id: str) -> bool | None:
    state = _load_state()
    entry = state.get(source_id, {})
    return entry.get("is_enabled_override")
