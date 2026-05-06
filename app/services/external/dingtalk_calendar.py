"""DingTalk calendar integration backed by the dws CLI."""
from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import settings

DwsRunner = Callable[[list[str], float], Awaitable[Any]]


class DwsCalendarError(RuntimeError):
    """Raised when dws cannot return a usable calendar response."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DingTalkCalendarService:
    """Read calendar events through `dws calendar` commands."""

    def __init__(
        self,
        *,
        runner: DwsRunner | None = None,
        dws_bin: str | None = None,
        timeout: float | None = None,
        timezone_name: str | None = None,
    ) -> None:
        self._runner = runner
        self._dws_bin = dws_bin or settings.DINGTALK_DWS_BIN
        self._timeout = timeout or settings.DINGTALK_DWS_TIMEOUT_SECONDS
        self._timezone_name = timezone_name or settings.DINGTALK_CALENDAR_TIMEZONE

    async def list_events(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        include_details: bool = True,
        max_detail_count: int = 50,
    ) -> dict[str, Any]:
        range_start, range_end = self._resolve_range(start, end)
        args = ["calendar", "event", "list"]
        if range_start is not None:
            args.extend(["--start", _format_datetime(range_start, self._timezone())])
        if range_end is not None:
            args.extend(["--end", _format_datetime(range_end, self._timezone())])
        args.extend(["--format", "json"])

        payload = await self._run(args)
        events = _extract_event_list(payload)

        normalized: list[dict[str, Any]] = []
        detail_budget = max(0, max_detail_count)
        for item in events:
            event = _normalize_event(item)
            if include_details and event["event_id"] and detail_budget > 0:
                detail_payload = await self._run(
                    [
                        "calendar",
                        "event",
                        "get",
                        "--id",
                        event["event_id"],
                        "--format",
                        "json",
                    ]
                )
                event = _merge_event_detail(event, detail_payload)
                detail_budget -= 1
            normalized.append(event)

        now = datetime.now(ZoneInfo("UTC"))
        return {
            "generated_at": now.isoformat(),
            "range_start": _format_datetime(range_start, self._timezone())
            if range_start is not None
            else None,
            "range_end": _format_datetime(range_end, self._timezone())
            if range_end is not None
            else None,
            "source": "dws",
            "count": len(normalized),
            "events": normalized,
        }

    async def get_event_detail(self, event_id: str) -> dict[str, Any]:
        event_id = event_id.strip()
        if not event_id:
            raise ValueError("event_id is required")

        payload = await self._run(
            ["calendar", "event", "get", "--id", event_id, "--format", "json"]
        )
        return _normalize_event(payload)

    async def _run(self, args: list[str]) -> Any:
        if self._runner is not None:
            return await self._runner(args, self._timeout)
        return await run_dws_json(self._dws_bin, args, timeout=self._timeout)

    def _resolve_range(
        self,
        start: datetime | None,
        end: datetime | None,
    ) -> tuple[datetime | None, datetime | None]:
        if start is not None or end is not None:
            return start, end

        tz = self._timezone()
        now = datetime.now(tz)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return today, today + timedelta(days=1)

    def _timezone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self._timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise DwsCalendarError(
                f"Invalid DingTalk calendar timezone: {self._timezone_name}",
                status_code=500,
            ) from exc


async def run_dws_json(dws_bin: str, args: list[str], *, timeout: float) -> Any:
    """Run dws and parse JSON stdout."""
    binary = shutil.which(dws_bin) if "/" not in dws_bin else dws_bin
    if not binary:
        raise DwsCalendarError(
            "DingTalk CLI not found. Install dws or set DINGTALK_DWS_BIN.",
            status_code=503,
        )

    try:
        process = await asyncio.create_subprocess_exec(
            binary,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise DwsCalendarError(
            "DingTalk CLI not found. Install dws or set DINGTALK_DWS_BIN.",
            status_code=503,
        ) from exc

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise DwsCalendarError("DingTalk CLI command timed out.", status_code=504) from exc

    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()
    if process.returncode != 0:
        detail = stderr_text or stdout_text or f"dws exited with code {process.returncode}"
        raise DwsCalendarError(detail, status_code=502)

    if not stdout_text:
        return {}
    try:
        return json.loads(stdout_text)
    except json.JSONDecodeError as exc:
        raise DwsCalendarError("DingTalk CLI returned non-JSON output.", status_code=502) from exc


def _format_datetime(value: datetime, default_tz: ZoneInfo) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=default_tz)
    return value.isoformat(timespec="seconds")


def _extract_event_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("events", "items", "result", "data", "list", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_event_list(value)
            if nested:
                return nested
    return []


def _normalize_event(raw: Any) -> dict[str, Any]:
    event = _extract_event_object(raw)
    start = event.get("start")
    end = event.get("end")
    return {
        "event_id": _first_text(event, "eventId", "event_id", "id", "scheduleId"),
        "title": _first_text(event, "summary", "title", "subject", "name"),
        "description": _first_text(event, "description", "body", "content", "desc"),
        "start": start,
        "end": end,
        "start_time": _extract_time(start) or _first_text(event, "startTime", "startDateTime"),
        "end_time": _extract_time(end) or _first_text(event, "endTime", "endDateTime"),
        "timezone": _first_text(event, "timezone", "timeZone"),
        "location": _extract_location(event.get("location")),
        "organizer": event.get("organizer") if isinstance(event.get("organizer"), dict) else None,
        "participants": _extract_list(event, "participants", "attendees"),
        "rooms": _extract_list(event, "rooms", "meetingRooms", "resources"),
        "raw": event,
    }


def _merge_event_detail(event: dict[str, Any], detail_payload: Any) -> dict[str, Any]:
    detail = _normalize_event(detail_payload)
    merged = event.copy()
    for key, value in detail.items():
        if key == "raw":
            continue
        if value not in (None, "", [], {}):
            merged[key] = value
    detail_event = _extract_event_object(detail_payload)
    if detail_event:
        raw = event.get("raw", {}).copy()
        raw.update(detail_event)
        merged["raw"] = raw
    return merged


def _extract_event_object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    event_keys = {
        "eventId",
        "event_id",
        "id",
        "scheduleId",
        "summary",
        "title",
        "subject",
        "name",
        "start",
        "end",
        "startTime",
        "endTime",
        "startDateTime",
        "endDateTime",
    }
    if any(key in payload for key in event_keys):
        return payload

    for key in ("event", "result", "data", "item", "record", "content"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            event = _extract_event_object(nested)
            if event:
                return event
    return payload


def _first_text(event: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return None


def _extract_time(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        return _first_text(value, "dateTime", "datetime", "date", "time")
    return None


def _extract_location(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        return _first_text(value, "displayName", "name", "address")
    return None


def _extract_list(event: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = event.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []
