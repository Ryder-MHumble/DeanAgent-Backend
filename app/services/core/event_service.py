"""Event service — CRUD operations for events data."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.schemas.event import (
    EventDetailResponse,
    EventListItem,
    EventListResponse,
    EventStatsResponse,
)

EVENTS_FILE = Path("data/scholars/events.json")


def _load_events() -> dict[str, Any]:
    """Load events data from JSON file."""
    if not EVENTS_FILE.exists():
        return {"total": 0, "last_updated": None, "events": []}

    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_events(data: dict[str, Any]) -> None:
    """Save events data to JSON file."""
    data["last_updated"] = datetime.now().isoformat()
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
    """Get paginated list of events with filtering."""
    data = _load_events()
    events = data.get("events", [])

    # Apply filters
    filtered = events

    if event_type:
        filtered = [e for e in filtered if e.get("event_type", "") == event_type]

    if speaker_name:
        name_lower = speaker_name.lower()
        filtered = [
            e for e in filtered
            if name_lower in e.get("speaker_name", "").lower()
        ]

    if start_date:
        filtered = [e for e in filtered if e.get("event_date", "") >= start_date]

    if end_date:
        filtered = [e for e in filtered if e.get("event_date", "") <= end_date]

    if scholar_id:
        filtered = [
            e for e in filtered
            if scholar_id in e.get("scholar_ids", [])
        ]

    if keyword:
        kw = keyword.lower()
        filtered = [
            e for e in filtered
            if kw in e.get("title", "").lower()
            or kw in e.get("abstract", "").lower()
            or kw in e.get("speaker_name", "").lower()
        ]

    # Sort by event date (newest first)
    filtered.sort(key=lambda x: x.get("event_date", ""), reverse=True)

    # Pagination
    total = len(filtered)
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    end = start + page_size
    items = filtered[start:end]

    # Convert to list items
    list_items = [
        EventListItem(
            id=evt.get("id", ""),
            event_type=evt.get("event_type", ""),
            title=evt.get("title", ""),
            speaker_name=evt.get("speaker_name", ""),
            speaker_organization=evt.get("speaker_organization", ""),
            event_date=evt.get("event_date", ""),
            location=evt.get("location", ""),
            series_number=evt.get("series_number", ""),
            scholar_count=len(evt.get("scholar_ids", [])),
            created_at=evt.get("created_at", ""),
        )
        for evt in items
    ]

    return EventListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=list_items,
    )


def get_event_detail(event_id: str) -> EventDetailResponse | None:
    """Get detailed information for a single event."""
    data = _load_events()
    events = data.get("events", [])

    for evt in events:
        if evt.get("id") == event_id:
            return EventDetailResponse(**evt)

    return None


def get_event_stats() -> EventStatsResponse:
    """Get statistics for all events."""
    data = _load_events()
    events = data.get("events", [])

    # Basic counts
    total = len(events)

    # By type
    by_type: dict[str, int] = {}
    for evt in events:
        evt_type = evt.get("event_type", "未分类")
        by_type[evt_type] = by_type.get(evt_type, 0) + 1

    # By month
    by_month: dict[str, int] = {}
    for evt in events:
        date_str = evt.get("event_date", "")
        if date_str:
            month = date_str[:7]  # YYYY-MM
            by_month[month] = by_month.get(month, 0) + 1

    # Unique speakers
    speakers = set(evt.get("speaker_name", "") for evt in events if evt.get("speaker_name"))
    total_speakers = len(speakers)

    # Average duration
    durations = [evt.get("duration", 0) for evt in events if evt.get("duration", 0) > 0]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    return EventStatsResponse(
        total=total,
        by_type=[{"event_type": k, "count": v} for k, v in by_type.items()],
        by_month=[{"month": k, "count": v} for k, v in sorted(by_month.items(), reverse=True)],
        total_speakers=total_speakers,
        avg_duration=round(avg_duration, 2),
    )


def create_event(evt_data: dict[str, Any]) -> EventDetailResponse:
    """Create a new event."""
    data = _load_events()
    events = data.get("events", [])

    # Generate UUID
    evt_data["id"] = str(uuid.uuid4())

    # Add timestamps
    now = datetime.now().isoformat()
    evt_data["created_at"] = now
    evt_data["updated_at"] = now

    events.append(evt_data)
    data["events"] = events
    data["total"] = len(events)

    _save_events(data)

    return EventDetailResponse(**evt_data)


def update_event(event_id: str, updates: dict[str, Any]) -> EventDetailResponse | None:
    """Update an existing event."""
    data = _load_events()
    events = data.get("events", [])

    for i, evt in enumerate(events):
        if evt.get("id") == event_id:
            # Apply updates
            for key, value in updates.items():
                if key != "id":  # Don't allow ID changes
                    evt[key] = value

            # Update timestamp
            evt["updated_at"] = datetime.now().isoformat()

            events[i] = evt
            data["events"] = events

            _save_events(data)

            return EventDetailResponse(**evt)

    return None


def delete_event(event_id: str) -> bool:
    """Delete an event."""
    data = _load_events()
    events = data.get("events", [])

    original_count = len(events)
    events = [e for e in events if e.get("id") != event_id]

    if len(events) < original_count:
        data["events"] = events
        data["total"] = len(events)
        _save_events(data)
        return True

    return False


def add_scholar_to_event(event_id: str, scholar_id: str) -> EventDetailResponse | None:
    """Add a scholar association to an event."""
    data = _load_events()
    events = data.get("events", [])

    for i, evt in enumerate(events):
        if evt.get("id") == event_id:
            scholar_ids = evt.get("scholar_ids", [])
            if scholar_id not in scholar_ids:
                scholar_ids.append(scholar_id)
                evt["scholar_ids"] = scholar_ids
                evt["updated_at"] = datetime.now().isoformat()

                events[i] = evt
                data["events"] = events
                _save_events(data)

            return EventDetailResponse(**evt)

    return None


def remove_scholar_from_event(event_id: str, scholar_id: str) -> EventDetailResponse | None:
    """Remove a scholar association from an event."""
    data = _load_events()
    events = data.get("events", [])

    for i, evt in enumerate(events):
        if evt.get("id") == event_id:
            scholar_ids = evt.get("scholar_ids", [])
            if scholar_id in scholar_ids:
                scholar_ids.remove(scholar_id)
                evt["scholar_ids"] = scholar_ids
                evt["updated_at"] = datetime.now().isoformat()

                events[i] = evt
                data["events"] = events
                _save_events(data)

            return EventDetailResponse(**evt)

    return None


def get_event_scholars(event_id: str) -> list[str] | None:
    """Get list of scholar IDs associated with an event."""
    data = _load_events()
    events = data.get("events", [])

    for evt in events:
        if evt.get("id") == event_id:
            return evt.get("scholar_ids", [])

    return None
