"""Event service — CRUD 操作（Supabase SDK）."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.event import (
    EventDetailResponse,
    EventListItem,
    EventListResponse,
    EventStatsResponse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client():
    from app.db.client import get_client  # noqa: PLC0415
    return get_client()


def _clean_date(v: Any) -> str | None:
    if not v or v == "":
        return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", str(v))
    return m.group(1) if m else None


def _clean(v: Any, t: str | None = None) -> Any:
    if v is None or v == "":
        return None
    if t == "int":
        try:
            return int(v)
        except Exception:
            return None
    return v


def _db_to_detail(row: dict) -> EventDetailResponse:
    """Map DB columns → EventDetailResponse (handles field name differences)."""
    return EventDetailResponse(
        id=row.get("id", ""),
        event_type=row.get("event_type") or "",
        series_number=str(row.get("series_number") or ""),
        speaker_name=row.get("speaker_name") or "",
        speaker_organization=row.get("speaker_organization") or "",
        speaker_position=row.get("speaker_title") or "",   # DB: speaker_title → schema: speaker_position
        speaker_bio=row.get("speaker_bio") or "",
        speaker_photo_url=row.get("speaker_photo_url") or "",
        title=row.get("title", ""),
        abstract=row.get("description") or "",             # DB: description → schema: abstract
        event_date=str(_clean_date(row.get("event_date")) or ""),
        duration=float(row.get("duration") or 0),
        location=row.get("location") or "",
        scholar_ids=row.get("scholar_ids") or [],
        publicity=row.get("publicity") or "",
        needs_email_invitation=row.get("needs_email_invitation") or False,
        certificate_number=row.get("certificate_number") or "",
        created_by=row.get("created_by") or "",
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
        audit_status=row.get("audit_status") or "",
    )


def _event_to_db_row(evt: dict) -> dict:
    """Convert API event dict to DB row (maps field names)."""
    return {
        "id": evt.get("id"),
        "title": evt.get("title", ""),
        "event_type": _clean(evt.get("event_type")),
        "series_number": _clean(evt.get("series_number"), "int"),
        "speaker_name": _clean(evt.get("speaker_name")),
        "speaker_organization": _clean(evt.get("speaker_organization")),
        "speaker_title": _clean(evt.get("speaker_position")),
        "speaker_bio": _clean(evt.get("speaker_bio")),
        "speaker_photo_url": _clean(evt.get("speaker_photo_url")),
        "description": _clean(evt.get("abstract")),
        "event_date": _clean_date(evt.get("event_date")),
        "location": _clean(evt.get("location")),
        "scholar_ids": evt.get("scholar_ids") or [],
        "is_past": evt.get("is_past", False),
        "created_at": _clean(evt.get("created_at")),
        "updated_at": _clean(evt.get("updated_at")),
    }


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

async def get_event_list(
    event_type: str | None = None,
    speaker_name: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    scholar_id: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> EventListResponse:
    client = _get_client()
    q = client.table("events").select("*").order("event_date", desc=True)
    if event_type:
        q = q.eq("event_type", event_type)
    if speaker_name:
        q = q.ilike("speaker_name", f"%{speaker_name}%")
    if start_date:
        q = q.gte("event_date", start_date)
    if end_date:
        q = q.lte("event_date", end_date)
    if keyword:
        q = q.or_(f"title.ilike.%{keyword}%,description.ilike.%{keyword}%,speaker_name.ilike.%{keyword}%")
    res = await q.execute()
    rows = res.data or []

    if scholar_id:
        rows = [r for r in rows if scholar_id in (r.get("scholar_ids") or [])]

    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    items = [
        EventListItem(
            id=r.get("id", ""),
            event_type=r.get("event_type") or "",
            title=r.get("title", ""),
            speaker_name=r.get("speaker_name") or "",
            speaker_organization=r.get("speaker_organization") or "",
            event_date=str(_clean_date(r.get("event_date")) or ""),
            location=r.get("location") or "",
            series_number=str(r.get("series_number") or ""),
            scholar_count=len(r.get("scholar_ids") or []),
            created_at=str(r.get("created_at") or ""),
        )
        for r in rows[start: start + page_size]
    ]
    return EventListResponse(total=total, page=page, page_size=page_size,
                             total_pages=total_pages, items=items)


async def get_event_detail(event_id: str) -> EventDetailResponse | None:
    client = _get_client()
    res = await client.table("events").select("*").eq("id", event_id).execute()
    if res.data:
        return _db_to_detail(res.data[0])
    return None


async def get_event_stats() -> EventStatsResponse:
    client = _get_client()
    res = await client.table("events").select(
        "event_type,event_date,speaker_name,scholar_ids"
    ).execute()
    rows = res.data or []
    by_type: dict[str, int] = {}
    by_month: dict[str, int] = {}
    speakers: set[str] = set()
    for r in rows:
        t = r.get("event_type") or "未分类"
        by_type[t] = by_type.get(t, 0) + 1
        d = _clean_date(r.get("event_date"))
        if d:
            m = d[:7]
            by_month[m] = by_month.get(m, 0) + 1
        if r.get("speaker_name"):
            speakers.add(r["speaker_name"])
    return EventStatsResponse(
        total=len(rows),
        by_type=[{"event_type": k, "count": v} for k, v in by_type.items()],
        by_month=[{"month": k, "count": v} for k, v in sorted(by_month.items(), reverse=True)],
        total_speakers=len(speakers),
        avg_duration=0.0,
    )


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

async def create_event(evt_data: dict[str, Any]) -> EventDetailResponse:
    now = datetime.now(timezone.utc).isoformat()
    evt_data["id"] = str(uuid.uuid4())
    evt_data.setdefault("created_at", now)
    evt_data.setdefault("updated_at", now)

    client = _get_client()
    await client.table("events").insert(_event_to_db_row(evt_data)).execute()
    return _db_to_detail(_event_to_db_row(evt_data) | {"id": evt_data["id"]})


async def update_event(event_id: str, updates: dict[str, Any]) -> EventDetailResponse | None:
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    db_updates = _event_to_db_row({**updates, "id": event_id})
    db_updates = {k: v for k, v in db_updates.items() if k != "id" and v is not None}

    client = _get_client()
    res = await client.table("events").update(db_updates).eq("id", event_id).execute()
    if res.data:
        return _db_to_detail(res.data[0])
    return None


async def delete_event(event_id: str) -> bool:
    client = _get_client()
    res = await client.table("events").delete().eq("id", event_id).execute()
    return bool(res.data)


async def add_scholar_to_event(event_id: str, scholar_id: str) -> EventDetailResponse | None:
    detail = await get_event_detail(event_id)
    if not detail:
        return None
    ids = list(detail.scholar_ids)
    if scholar_id not in ids:
        ids.append(scholar_id)
    return await update_event(event_id, {"scholar_ids": ids})


async def remove_scholar_from_event(event_id: str, scholar_id: str) -> EventDetailResponse | None:
    detail = await get_event_detail(event_id)
    if not detail:
        return None
    ids = [i for i in detail.scholar_ids if i != scholar_id]
    return await update_event(event_id, {"scholar_ids": ids})


async def get_event_scholars(event_id: str) -> list[str] | None:
    detail = await get_event_detail(event_id)
    return detail.scholar_ids if detail else None
