from __future__ import annotations

import asyncio
import os
import shutil
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from app.scheduler.manager import get_scheduler_manager
from app.schemas.console import (
    ConsoleDailyTrendPoint,
    ConsoleDimensionSummary,
    ConsoleOverviewResponse,
    ConsoleRecentRun,
    ConsoleServerMetrics,
    ConsoleSourceLogsResponse,
    ConsoleTodayStats,
)
from app.services import crawl_service, source_service
from app.services.crawler_control_service import get_control_service
from app.services.stores.crawl_log_store import get_crawl_logs, get_crawl_logs_since

CONSOLE_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _local_day_bounds(target_day: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(target_day, time.min, tzinfo=CONSOLE_TIMEZONE)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _now_local_day() -> date:
    return datetime.now(CONSOLE_TIMEZONE).date()


def _read_proc_stat_snapshot() -> tuple[int, int]:
    with open("/proc/stat", "r", encoding="utf-8") as handle:
        cpu_line = handle.readline().strip().split()

    values = [int(value) for value in cpu_line[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return total, idle


async def _sample_cpu_percent() -> float:
    try:
        total_before, idle_before = _read_proc_stat_snapshot()
        await asyncio.sleep(0.12)
        total_after, idle_after = _read_proc_stat_snapshot()
    except (FileNotFoundError, OSError, ValueError):
        return 0.0

    total_delta = max(total_after - total_before, 0)
    idle_delta = max(idle_after - idle_before, 0)
    if total_delta == 0:
        return 0.0
    busy_ratio = 1 - (idle_delta / total_delta)
    return round(max(0.0, min(100.0, busy_ratio * 100)), 2)


def _read_memory_percent() -> float:
    try:
        metrics: dict[str, int] = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                key, _, remainder = line.partition(":")
                value = remainder.strip().split()[0]
                metrics[key] = int(value)
    except (FileNotFoundError, OSError, ValueError, IndexError):
        return 0.0

    total_kb = metrics.get("MemTotal", 0)
    available_kb = metrics.get("MemAvailable", metrics.get("MemFree", 0))
    if total_kb <= 0:
        return 0.0
    used_ratio = 1 - (available_kb / total_kb)
    return round(max(0.0, min(100.0, used_ratio * 100)), 2)


def _read_uptime_seconds() -> int:
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as handle:
            raw_value = handle.readline().split()[0]
        return max(int(float(raw_value)), 0)
    except (FileNotFoundError, OSError, ValueError, IndexError):
        return 0


def _build_today_stats(logs: list[dict[str, Any]], *, target_day: date) -> ConsoleTodayStats:
    durations = [
        float(log.get("duration_seconds") or 0.0)
        for log in logs
        if log.get("duration_seconds") is not None
    ]
    finished_times = [
        _parse_dt(log.get("finished_at")) or _parse_dt(log.get("started_at"))
        for log in logs
    ]
    finished_times = [dt for dt in finished_times if dt is not None]

    return ConsoleTodayStats(
        date=target_day,
        timezone="Asia/Shanghai",
        total_runs=len(logs),
        successful_runs=sum(1 for log in logs if str(log.get("status")) == "success"),
        failed_runs=sum(1 for log in logs if str(log.get("status")) == "failed"),
        no_new_content_runs=sum(
            1 for log in logs if str(log.get("status")) == "no_new_content"
        ),
        unique_sources=len({str(log.get("source_id") or "") for log in logs if log.get("source_id")}),
        total_items=sum(int(log.get("items_total") or 0) for log in logs),
        new_items=sum(int(log.get("items_new") or 0) for log in logs),
        average_duration_seconds=round(mean(durations), 2) if durations else 0.0,
        last_run_at=max(finished_times) if finished_times else None,
    )


async def get_console_overview(*, recent_run_limit: int = 12) -> ConsoleOverviewResponse:
    target_day = _now_local_day()
    day_start, _ = _local_day_bounds(target_day)

    health = await crawl_service.get_crawl_health()
    catalog = await source_service.list_sources_catalog(
        page=1,
        page_size=500,
        include_facets=False,
        sort_by="dimension_priority",
        order="asc",
    )
    source_rows = catalog.get("items", [])
    source_map = {str(row.get("id") or ""): row for row in source_rows}

    today_logs = await get_crawl_logs_since(since=day_start, limit=5000)
    recent_logs = await get_crawl_logs(limit=recent_run_limit)

    dimension_stats_map: dict[str, dict[str, Any]] = {}
    for row in source_rows:
        dimension = str(row.get("dimension") or "unknown")
        bucket = dimension_stats_map.setdefault(
            dimension,
            {
                "dimension": dimension,
                "dimension_name": row.get("dimension_name"),
                "total_sources": 0,
                "enabled_sources": 0,
                "healthy_sources": 0,
                "warning_sources": 0,
                "failing_sources": 0,
                "today_runs": 0,
                "today_new_items": 0,
                "last_run_at": None,
            },
        )
        bucket["total_sources"] += 1
        if row.get("is_enabled"):
            bucket["enabled_sources"] += 1

        health_status = str(row.get("health_status") or "unknown")
        if health_status == "healthy":
            bucket["healthy_sources"] += 1
        elif health_status == "warning":
            bucket["warning_sources"] += 1
        elif health_status == "failing":
            bucket["failing_sources"] += 1

        last_crawl_at = _parse_dt(row.get("last_crawl_at"))
        if last_crawl_at and (
            bucket["last_run_at"] is None or last_crawl_at > bucket["last_run_at"]
        ):
            bucket["last_run_at"] = last_crawl_at

    for log in today_logs:
        source_id = str(log.get("source_id") or "")
        row = source_map.get(source_id)
        dimension = str((row or {}).get("dimension") or "unknown")
        bucket = dimension_stats_map.setdefault(
            dimension,
            {
                "dimension": dimension,
                "dimension_name": (row or {}).get("dimension_name"),
                "total_sources": 0,
                "enabled_sources": 0,
                "healthy_sources": 0,
                "warning_sources": 0,
                "failing_sources": 0,
                "today_runs": 0,
                "today_new_items": 0,
                "last_run_at": None,
            },
        )
        bucket["today_runs"] += 1
        bucket["today_new_items"] += int(log.get("items_new") or 0)
        finished_at = _parse_dt(log.get("finished_at")) or _parse_dt(log.get("started_at"))
        if finished_at and (bucket["last_run_at"] is None or finished_at > bucket["last_run_at"]):
            bucket["last_run_at"] = finished_at

    recent_runs = [
        ConsoleRecentRun(
            source_id=str(log.get("source_id") or ""),
            source_name=(source_map.get(str(log.get("source_id") or "")) or {}).get("name"),
            dimension=(source_map.get(str(log.get("source_id") or "")) or {}).get("dimension"),
            dimension_name=(source_map.get(str(log.get("source_id") or "")) or {}).get(
                "dimension_name"
            ),
            status=str(log.get("status") or "unknown"),
            items_total=int(log.get("items_total") or 0),
            items_new=int(log.get("items_new") or 0),
            error_message=log.get("error_message"),
            started_at=_parse_dt(log.get("started_at")),
            finished_at=_parse_dt(log.get("finished_at")),
            duration_seconds=(
                float(log.get("duration_seconds"))
                if log.get("duration_seconds") is not None
                else None
            ),
        )
        for log in recent_logs
    ]

    scheduler = get_scheduler_manager()
    return ConsoleOverviewResponse(
        generated_at=datetime.now(timezone.utc),
        scheduler_status="running" if scheduler else "not_started",
        health=health,
        today=_build_today_stats(today_logs, target_day=target_day),
        manual_job=get_control_service().get_status(),
        dimension_stats=[
            ConsoleDimensionSummary(**item)
            for item in sorted(
                dimension_stats_map.values(),
                key=lambda item: (-int(item["enabled_sources"]), str(item["dimension"])),
            )
        ],
        recent_runs=recent_runs,
    )


async def get_console_source_logs(source_id: str, *, limit: int = 20) -> ConsoleSourceLogsResponse:
    source = await source_service.get_source(source_id)
    if source is None:
        raise ValueError(f"Source not found: {source_id}")
    logs = await crawl_service.get_crawl_logs(source_id=source_id, limit=limit)
    return ConsoleSourceLogsResponse(source_id=source_id, logs=logs)


async def get_console_daily_trend(*, days: int = 7) -> list[ConsoleDailyTrendPoint]:
    safe_days = max(1, min(days, 30))
    end_day = _now_local_day()
    start_day = end_day - timedelta(days=safe_days - 1)
    range_start, _ = _local_day_bounds(start_day)
    logs = await get_crawl_logs_since(since=range_start, limit=10000)

    grouped: dict[date, dict[str, int]] = defaultdict(
        lambda: {
            "crawls": 0,
            "success": 0,
            "failed": 0,
            "no_new_content": 0,
            "new_items": 0,
            "total_items": 0,
        }
    )

    for log in logs:
        started_at = _parse_dt(log.get("started_at")) or _parse_dt(log.get("finished_at"))
        if started_at is None:
            continue
        day_key = started_at.astimezone(CONSOLE_TIMEZONE).date()
        if day_key < start_day or day_key > end_day:
            continue
        bucket = grouped[day_key]
        bucket["crawls"] += 1
        status = str(log.get("status") or "")
        if status == "success":
            bucket["success"] += 1
        elif status == "failed":
            bucket["failed"] += 1
        elif status == "no_new_content":
            bucket["no_new_content"] += 1
        bucket["new_items"] += int(log.get("items_new") or 0)
        bucket["total_items"] += int(log.get("items_total") or 0)

    points: list[ConsoleDailyTrendPoint] = []
    for offset in range(safe_days):
        day_key = start_day + timedelta(days=offset)
        bucket = grouped[day_key]
        points.append(ConsoleDailyTrendPoint(date=day_key, **bucket))
    return points


async def get_console_server_metrics() -> ConsoleServerMetrics:
    disk_usage = shutil.disk_usage("/")
    try:
        load_average_1m = round(os.getloadavg()[0], 2)
    except OSError:
        load_average_1m = 0.0

    return ConsoleServerMetrics(
        cpu_percent=await _sample_cpu_percent(),
        memory_percent=_read_memory_percent(),
        disk_percent=round((disk_usage.used / disk_usage.total) * 100, 2)
        if disk_usage.total
        else 0.0,
        load_average_1m=load_average_1m,
        cpu_count=os.cpu_count() or 0,
        uptime_seconds=_read_uptime_seconds(),
        sampled_at=datetime.now(timezone.utc),
    )
