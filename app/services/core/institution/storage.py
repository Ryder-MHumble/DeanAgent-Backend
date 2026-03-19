"""Data storage layer for institutions.

Handles reading from and writing to Supabase database.
"""

from __future__ import annotations

import logging
from typing import Final

from app.db.client import get_client

logger = logging.getLogger(__name__)

_INSTITUTION_COLUMNS_CACHE: set[str] | None = None
_FALLBACK_INSTITUTION_COLUMNS: Final[set[str]] = {
    "id",
    "name",
    "type",
    "entity_type",
    "region",
    "org_type",
    "classification",
    "sub_classification",
    "group",
    "category",
    "priority",
    "scholar_count",
    "student_count_24",
    "student_count_25",
    "student_count_total",
    "mentor_count",
    "resident_leaders",
    "degree_committee",
    "teaching_committee",
    "university_leaders",
    "notable_scholars",
    "parent_id",
    "avatar",
    "org_name",
    "created_at",
    "updated_at",
}


async def _get_institution_columns(*, force_refresh: bool = False) -> set[str]:
    """Get current institutions table columns.

    Supabase/PostgREST will return PGRST204 when upsert payload contains fields
    that do not exist in the table schema. We cache columns to prune payloads
    before write, preventing 500 errors on PATCH/POST.
    """
    global _INSTITUTION_COLUMNS_CACHE

    if _INSTITUTION_COLUMNS_CACHE and not force_refresh:
        return _INSTITUTION_COLUMNS_CACHE

    client = get_client()
    resp = await client.table("institutions").select("*").limit(1).execute()
    first_row = resp.data[0] if resp.data else None

    if first_row:
        _INSTITUTION_COLUMNS_CACHE = set(first_row.keys())
    else:
        _INSTITUTION_COLUMNS_CACHE = set(_FALLBACK_INSTITUTION_COLUMNS)

    return _INSTITUTION_COLUMNS_CACHE


async def fetch_all_institutions() -> list[dict]:
    """Fetch all institution records from database.

    Returns:
        List of institution records as dicts
    """
    client = get_client()
    resp = await client.table("institutions").select("*").execute()
    return resp.data


async def fetch_institution_by_id(institution_id: str) -> dict | None:
    """Fetch a single institution by ID.

    Args:
        institution_id: Institution ID

    Returns:
        Institution record or None if not found
    """
    client = get_client()
    resp = await client.table("institutions").select("*").eq("id", institution_id).execute()
    return resp.data[0] if resp.data else None


async def upsert_institution(institution_data: dict) -> dict:
    """Insert or update an institution record.

    Args:
        institution_data: Institution data dict (must include 'id')

    Returns:
        Upserted institution record
    """
    if "id" not in institution_data:
        raise ValueError("institution_data must include id")

    columns = await _get_institution_columns()
    payload = {k: v for k, v in institution_data.items() if k in columns}

    dropped_keys = sorted(set(institution_data.keys()) - set(payload.keys()))
    if dropped_keys:
        logger.warning(
            "Skipping unsupported institution columns for id=%s: %s",
            institution_data.get("id"),
            ", ".join(dropped_keys),
        )

    client = get_client()
    resp = await client.table("institutions").upsert(payload).execute()
    return resp.data[0]


async def delete_institution_by_id(institution_id: str) -> bool:
    """Delete an institution by ID.

    Args:
        institution_id: Institution ID

    Returns:
        True if deleted, False if not found
    """
    client = get_client()
    resp = await client.table("institutions").delete().eq("id", institution_id).execute()
    return len(resp.data) > 0
