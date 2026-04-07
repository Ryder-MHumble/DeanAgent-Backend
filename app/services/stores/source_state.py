"""Manage mutable source runtime state — backed by Supabase SDK.

Falls back to the original local JSON file when the Supabase client is not
initialised (e.g. during unit-tests or when SUPABASE_DB_URL is empty).

DB table: source_states
  source_id VARCHAR(128) PRIMARY KEY
  source_name VARCHAR(256)
  source_url TEXT
  dimension VARCHAR(64)
  dimension_name VARCHAR(128)
  taxonomy_version VARCHAR(16)
  taxonomy_domain VARCHAR(64)
  taxonomy_domain_name VARCHAR(128)
  taxonomy_track VARCHAR(64)
  taxonomy_track_name VARCHAR(128)
  taxonomy_scope VARCHAR(64)
  taxonomy_scope_name VARCHAR(128)
  group_name VARCHAR(128)
  source_file VARCHAR(128)
  crawl_method VARCHAR(64)
  crawler_class VARCHAR(128)
  schedule VARCHAR(32)
  crawl_interval_minutes INTEGER
  source_type VARCHAR(64)
  source_platform VARCHAR(64)
  tags TEXT[]
  is_enabled_default BOOLEAN
  is_supported BOOLEAN
  institution_name VARCHAR(256)
  institution_tier VARCHAR(32)
  last_crawl_at TIMESTAMPTZ
  last_success_at TIMESTAMPTZ
  consecutive_failures SMALLINT DEFAULT 0
  is_enabled_override BOOLEAN  -- NULL = no override
  updated_at TIMESTAMPTZ

State file (fallback): data/state/source_state.json
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from app.config import BASE_DIR
from app.services.core.source_catalog_meta import build_source_catalog_meta

logger = logging.getLogger(__name__)

STATE_DIR = BASE_DIR / "data" / "state"
STATE_FILE = STATE_DIR / "source_state.json"

_lock = Lock()  # used only for JSON fallback path


# ---------------------------------------------------------------------------
# JSON fallback helpers
# ---------------------------------------------------------------------------

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


def _get_client():
    from app.db.client import get_client  # noqa: PLC0415
    return get_client()


def _build_catalog_row_from_config(config: dict[str, Any], now_iso: str) -> dict[str, Any]:
    source_id = str(config.get("id") or "").strip()
    meta = build_source_catalog_meta(config)
    return {
        "source_id": source_id,
        "source_name": meta.get("source_name"),
        "source_url": meta.get("source_url"),
        "dimension": meta.get("dimension"),
        "dimension_name": meta.get("dimension_name"),
        "taxonomy_version": meta.get("taxonomy_version"),
        "taxonomy_domain": meta.get("taxonomy_domain"),
        "taxonomy_domain_name": meta.get("taxonomy_domain_name"),
        "taxonomy_track": meta.get("taxonomy_track"),
        "taxonomy_track_name": meta.get("taxonomy_track_name"),
        "taxonomy_scope": meta.get("taxonomy_scope"),
        "taxonomy_scope_name": meta.get("taxonomy_scope_name"),
        "group_name": meta.get("group_name"),
        "source_file": meta.get("source_file"),
        "crawl_method": meta.get("crawl_method"),
        "crawler_class": meta.get("crawler_class"),
        "schedule": meta.get("schedule"),
        "crawl_interval_minutes": meta.get("crawl_interval_minutes"),
        "source_type": meta.get("source_type"),
        "source_platform": meta.get("source_platform"),
        "tags": meta.get("tags") or [],
        "is_enabled_default": bool(meta.get("is_enabled_default", True)),
        "is_supported": True,
        "institution_name": meta.get("institution_name"),
        "institution_tier": meta.get("institution_tier"),
        "updated_at": now_iso,
    }


def _is_missing_source_states_column_error(exc: Exception) -> bool:
    text = str(exc)
    return (
        "column of 'source_states'" in text
        and "Could not find the '" in text
    )


def _build_minimal_runtime_row(source_id: str, now_iso: str) -> dict[str, Any]:
    # Backward compatibility: some deployed DBs only keep runtime state columns.
    return {
        "source_id": source_id,
        "updated_at": now_iso,
    }


def _strip_taxonomy_fields(row: dict[str, Any]) -> dict[str, Any]:
    taxonomy_keys = {
        "taxonomy_version",
        "taxonomy_domain",
        "taxonomy_domain_name",
        "taxonomy_track",
        "taxonomy_track_name",
        "taxonomy_scope",
        "taxonomy_scope_name",
    }
    return {key: value for key, value in row.items() if key not in taxonomy_keys}


# ---------------------------------------------------------------------------
# Public API  (all async — callers must await)
# ---------------------------------------------------------------------------

async def get_source_state(source_id: str) -> dict[str, Any]:
    try:
        client = _get_client()
        res = await client.table("source_states").select("*").eq("source_id", source_id).execute()
        if res.data:
            return res.data[0]
        return {}
    except RuntimeError:
        return _load_state().get(source_id, {})
    except Exception as exc:
        logger.warning("get_source_state DB failed, using JSON: %s", exc)
        return _load_state().get(source_id, {})


async def get_all_source_states() -> dict[str, dict[str, Any]]:
    try:
        client = _get_client()
        res = await client.table("source_states").select("*").execute()
        return {row["source_id"]: row for row in (res.data or [])}
    except RuntimeError:
        return _load_state()
    except Exception as exc:
        logger.warning("get_all_source_states DB failed, using JSON: %s", exc)
        return _load_state()


async def sync_source_catalog_from_configs(
    source_configs: list[dict[str, Any]] | None = None,
    *,
    mark_missing_unsupported: bool = True,
) -> dict[str, Any]:
    """Sync all configured sources into source_states as catalog metadata."""
    if source_configs is None:
        from app.scheduler.manager import load_all_source_configs  # noqa: PLC0415

        source_configs = load_all_source_configs()

    from app.scheduler.manager import is_schedulable_source  # noqa: PLC0415

    schedulable_configs = [cfg for cfg in source_configs if is_schedulable_source(cfg)]

    now_iso = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    supported_ids: set[str] = set()
    for config in schedulable_configs:
        source_id = str(config.get("id") or "").strip()
        if not source_id:
            continue
        row = _build_catalog_row_from_config(config, now_iso)
        rows.append(row)
        supported_ids.add(source_id)

    try:
        client = _get_client()
        used_minimal_schema = False
        used_legacy_schema = False
        if rows:
            try:
                await client.table("source_states").upsert(
                    rows, on_conflict="source_id"
                ).execute()
            except Exception as exc:
                if not _is_missing_source_states_column_error(exc):
                    raise
                logger.warning(
                    "source_states schema misses some catalog columns; "
                    "retrying with legacy-compatible fields: %s",
                    exc,
                )
                legacy_rows = [_strip_taxonomy_fields(row) for row in rows]
                try:
                    await client.table("source_states").upsert(
                        legacy_rows, on_conflict="source_id"
                    ).execute()
                    used_legacy_schema = True
                except Exception as legacy_exc:
                    if not _is_missing_source_states_column_error(legacy_exc):
                        raise
                    used_minimal_schema = True
                    logger.warning(
                        "source_states schema is minimal; syncing runtime keys only: %s",
                        legacy_exc,
                    )
                    minimal_rows = [
                        _build_minimal_runtime_row(row["source_id"], now_iso)
                        for row in rows
                    ]
                    await client.table("source_states").upsert(
                        minimal_rows, on_conflict="source_id"
                    ).execute()

        marked_unsupported = 0
        deleted_missing = 0
        if mark_missing_unsupported:
            try:
                res = await client.table("source_states").select("source_id,is_supported").execute()
            except Exception as exc:
                if not _is_missing_source_states_column_error(exc):
                    raise
                used_minimal_schema = True
                res = await client.table("source_states").select("source_id").execute()

            for item in (res.data or []):
                source_id = str(item.get("source_id") or "").strip()
                if not source_id:
                    continue
                if source_id not in supported_ids:
                    if (not used_minimal_schema) and item.get("is_supported", True):
                        marked_unsupported += 1
                    await (
                        client.table("source_states")
                        .delete()
                        .eq("source_id", source_id)
                        .execute()
                    )
                    deleted_missing += 1

        return {
            "total_configs": len(schedulable_configs),
            "upserted": len(rows),
            "marked_unsupported": marked_unsupported,
            "deleted_missing": deleted_missing,
            "schema_mode": (
                "minimal"
                if used_minimal_schema
                else "legacy"
                if used_legacy_schema
                else "full"
            ),
        }
    except RuntimeError:
        pass
    except Exception as exc:
        logger.warning("sync_source_catalog_from_configs DB failed, using JSON: %s", exc)

    # JSON fallback
    with _lock:
        state = _load_state()
        for row in rows:
            source_id = row["source_id"]
            entry = state.setdefault(source_id, {})
            for key, value in row.items():
                if key == "source_id":
                    continue
                entry[key] = value

        marked_unsupported = 0
        deleted_missing = 0
        if mark_missing_unsupported:
            for source_id, entry in list(state.items()):
                if source_id not in supported_ids and entry.get("is_supported", True):
                    marked_unsupported += 1
                if source_id not in supported_ids:
                    state.pop(source_id, None)
                    deleted_missing += 1

        _save_state(state)
        return {
            "total_configs": len(schedulable_configs),
            "upserted": len(rows),
            "marked_unsupported": marked_unsupported,
            "deleted_missing": deleted_missing,
        }


async def update_source_state(
    source_id: str,
    *,
    last_crawl_at: datetime | None = None,
    last_success_at: datetime | None = None,
    consecutive_failures: int | None = None,
    reset_failures: bool = False,
) -> None:
    now = datetime.now(timezone.utc).isoformat()

    try:
        client = _get_client()

        # Read current failures to increment if needed
        res = await client.table("source_states").select("consecutive_failures").eq(
            "source_id", source_id
        ).execute()
        current_failures: int = 0
        if res.data:
            current_failures = res.data[0].get("consecutive_failures") or 0

        if reset_failures:
            new_failures = 0
        elif consecutive_failures is not None:
            new_failures = consecutive_failures
        else:
            new_failures = current_failures + 1

        row: dict[str, Any] = {
            "source_id": source_id,
            "consecutive_failures": new_failures,
            "updated_at": now,
        }
        if last_crawl_at is not None:
            row["last_crawl_at"] = last_crawl_at.isoformat()
        if last_success_at is not None:
            row["last_success_at"] = last_success_at.isoformat()

        await client.table("source_states").upsert(row, on_conflict="source_id").execute()
        return
    except RuntimeError:
        pass
    except Exception as exc:
        logger.warning("update_source_state DB failed, using JSON: %s", exc)

    # JSON fallback
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


async def set_enabled_override(source_id: str, is_enabled: bool) -> None:
    try:
        client = _get_client()
        row = {
            "source_id": source_id,
            "is_enabled_override": is_enabled,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await client.table("source_states").upsert(row, on_conflict="source_id").execute()
        return
    except RuntimeError:
        pass
    except Exception as exc:
        logger.warning("set_enabled_override DB failed, using JSON: %s", exc)

    with _lock:
        state = _load_state()
        entry = state.setdefault(source_id, {})
        entry["is_enabled_override"] = is_enabled
        _save_state(state)


async def get_enabled_override(source_id: str) -> bool | None:
    try:
        client = _get_client()
        res = await client.table("source_states").select("is_enabled_override").eq(
            "source_id", source_id
        ).execute()
        if res.data:
            return res.data[0].get("is_enabled_override")
        return None
    except RuntimeError:
        state = _load_state()
        return state.get(source_id, {}).get("is_enabled_override")
    except Exception as exc:
        logger.warning("get_enabled_override DB failed, using JSON: %s", exc)
        state = _load_state()
        return state.get(source_id, {}).get("is_enabled_override")
