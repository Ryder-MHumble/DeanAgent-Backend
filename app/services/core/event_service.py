"""Event service — CRUD 操作（Supabase SDK，JSON 降级）."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.event import (
    EventDetailResponse,
    EventListItem,
    EventListResponse,
    EventStatsResponse,
)

EVENTS_FILE = Path("data/scholars/events.json")
INSTITUTIONS_FILE = Path("data/scholars/institutions.json")


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


def _json_to_detail(evt: dict) -> EventDetailResponse:
    return EventDetailResponse(**evt)


# ---------------------------------------------------------------------------
# JSON fallback helpers
# ---------------------------------------------------------------------------

def _load_events_json() -> list[dict[str, Any]]:
    if EVENTS_FILE.exists():
        try:
            raw = json.load(open(EVENTS_FILE, encoding="utf-8"))
            return raw if isinstance(raw, list) else raw.get("events", [])
        except Exception:
            pass
    if not INSTITUTIONS_FILE.exists():
        return []
    with open(INSTITUTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("events", [])


def _save_events_json(events: list[dict[str, Any]]) -> None:
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"events": events, "last_updated": datetime.now(timezone.utc).isoformat()},
                  f, ensure_ascii=False, indent=2)


def _event_to_db_row(evt: dict) -> dict:
    """Convert JSON/API event dict to DB row (maps field names)."""
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

def get_event_list(
    event_type: str | None = None,
    speaker_name: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    scholar_id: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> EventListResponse:
    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()

        async def _fetch():
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
            return res.data or []

        rows = asyncio.get_event_loop().run_until_complete(_fetch())

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
    except RuntimeError:
        pass
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB get_event_list failed: %s", exc)

    # JSON fallback
    events = _load_events_json()
    if event_type:
        events = [e for e in events if e.get("event_type") == event_type]
    if speaker_name:
        events = [e for e in events if speaker_name.lower() in e.get("speaker_name", "").lower()]
    if start_date:
        events = [e for e in events if e.get("event_date", "") >= start_date]
    if end_date:
        events = [e for e in events if e.get("event_date", "") <= end_date]
    if scholar_id:
        events = [e for e in events if scholar_id in e.get("scholar_ids", [])]
    if keyword:
        kw = keyword.lower()
        events = [e for e in events
                  if kw in e.get("title", "").lower()
                  or kw in e.get("abstract", "").lower()
                  or kw in e.get("speaker_name", "").lower()]
    events.sort(key=lambda x: x.get("event_date", ""), reverse=True)
    total = len(events)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    items = [
        EventListItem(
            id=e.get("id", ""), event_type=e.get("event_type", ""),
            title=e.get("title", ""), speaker_name=e.get("speaker_name", ""),
            speaker_organization=e.get("speaker_organization", ""),
            event_date=e.get("event_date", ""), location=e.get("location", ""),
            series_number=str(e.get("series_number", "")),
            scholar_count=len(e.get("scholar_ids", [])),
            created_at=e.get("created_at", ""),
        )
        for e in events[start: start + page_size]
    ]
    return EventListResponse(total=total, page=page, page_size=page_size,
                             total_pages=total_pages, items=items)


def get_event_detail(event_id: str) -> EventDetailResponse | None:
    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()
        res = asyncio.get_event_loop().run_until_complete(
            client.table("events").select("*").eq("id", event_id).execute()
        )
        if res.data:
            return _db_to_detail(res.data[0])
        return None
    except RuntimeError:
        pass
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB get_event_detail failed: %s", exc)

    for evt in _load_events_json():
        if evt.get("id") == event_id:
            return _json_to_detail(evt)
    return None


def get_event_stats() -> EventStatsResponse:
    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()
        res = asyncio.get_event_loop().run_until_complete(
            client.table("events").select("event_type,event_date,speaker_name,scholar_ids").execute()
        )
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
    except RuntimeError:
        pass
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB get_event_stats failed: %s", exc)

    events = _load_events_json()
    by_type: dict[str, int] = {}
    by_month: dict[str, int] = {}
    speakers: set[str] = set()
    for e in events:
        t = e.get("event_type", "未分类")
        by_type[t] = by_type.get(t, 0) + 1
        d = e.get("event_date", "")
        if d:
            by_month[d[:7]] = by_month.get(d[:7], 0) + 1
        if e.get("speaker_name"):
            speakers.add(e["speaker_name"])
    durations = [e.get("duration", 0) for e in events if e.get("duration", 0) > 0]
    avg = sum(durations) / len(durations) if durations else 0.0
    return EventStatsResponse(
        total=len(events),
        by_type=[{"event_type": k, "count": v} for k, v in by_type.items()],
        by_month=[{"month": k, "count": v} for k, v in sorted(by_month.items(), reverse=True)],
        total_speakers=len(speakers),
        avg_duration=round(avg, 2),
    )


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def create_event(evt_data: dict[str, Any]) -> EventDetailResponse:
    now = datetime.now(timezone.utc).isoformat()
    evt_data["id"] = str(uuid.uuid4())
    evt_data.setdefault("created_at", now)
    evt_data.setdefault("updated_at", now)

    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()
        asyncio.get_event_loop().run_until_complete(
            client.table("events").insert(_event_to_db_row(evt_data)).execute()
        )
    except RuntimeError:
        pass
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB create_event failed: %s", exc)

    events = _load_events_json()
    events.append(evt_data)
    _save_events_json(events)
    return _json_to_detail(evt_data)


def update_event(event_id: str, updates: dict[str, Any]) -> EventDetailResponse | None:
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    db_updates = _event_to_db_row({**updates, "id": event_id})
    db_updates = {k: v for k, v in db_updates.items() if k != "id" and v is not None}

    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()
        res = asyncio.get_event_loop().run_until_complete(
            client.table("events").update(db_updates).eq("id", event_id).execute()
        )
        if res.data:
            return _db_to_detail(res.data[0])
    except RuntimeError:
        pass
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB update_event failed: %s", exc)

    events = _load_events_json()
    for i, evt in enumerate(events):
        if evt.get("id") == event_id:
            evt.update({k: v for k, v in updates.items() if k != "id"})
            events[i] = evt
            _save_events_json(events)
            return _json_to_detail(evt)
    return None


def delete_event(event_id: str) -> bool:
    deleted = False
    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()
        res = asyncio.get_event_loop().run_until_complete(
            client.table("events").delete().eq("id", event_id).execute()
        )
        deleted = bool(res.data)
    except RuntimeError:
        pass
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB delete_event failed: %s", exc)

    events = _load_events_json()
    filtered = [e for e in events if e.get("id") != event_id]
    if len(filtered) < len(events):
        _save_events_json(filtered)
        return True
    return deleted


def add_scholar_to_event(event_id: str, scholar_id: str) -> EventDetailResponse | None:
    detail = get_event_detail(event_id)
    if not detail:
        return None
    ids = list(detail.scholar_ids)
    if scholar_id not in ids:
        ids.append(scholar_id)
    return update_event(event_id, {"scholar_ids": ids})


def remove_scholar_from_event(event_id: str, scholar_id: str) -> EventDetailResponse | None:
    detail = get_event_detail(event_id)
    if not detail:
        return None
    ids = [i for i in detail.scholar_ids if i != scholar_id]
    return update_event(event_id, {"scholar_ids": ids})


def get_event_scholars(event_id: str) -> list[str] | None:
    detail = get_event_detail(event_id)
    return detail.scholar_ids if detail else None
