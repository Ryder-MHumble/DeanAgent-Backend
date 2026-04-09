from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from pathlib import Path
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.config import BASE_DIR
from app.scheduler.manager import get_scheduler_manager
from app.schemas.console import (
    ConsoleApiRecentCall,
    ConsoleApiUsageAvailableFilters,
    ConsoleApiUsageModelItem,
    ConsoleApiUsageModuleItem,
    ConsoleApiUsageOverview,
    ConsoleApiUsageResponse,
    ConsoleApiUsageScope,
    ConsoleApiUsageStageItem,
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
from app.services.llm.llm_call_tracker import CALLS_LOG_FILE, PRICING_MAP
from app.services.stores.crawl_log_store import get_crawl_logs, get_crawl_logs_since
from app.services.stores.crawl_runtime_store import get_crawl_runtime_state

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


def _resolve_console_job_status() -> dict[str, Any]:
    """Prefer in-process manual job, fallback to persisted full-run runtime state."""
    manual_status = get_control_service().get_status()
    if bool(manual_status.get("is_running")):
        return manual_status

    runtime_status = get_crawl_runtime_state()
    if not bool(runtime_status.get("is_running")):
        return manual_status

    return {
        "is_running": True,
        "current_source": runtime_status.get("current_source"),
        "completed_sources": list(runtime_status.get("completed_sources") or []),
        "failed_sources": list(runtime_status.get("failed_sources") or []),
        "requested_source_count": int(runtime_status.get("requested_source_count") or 0),
        "completed_count": int(runtime_status.get("completed_count") or 0),
        "failed_count": int(runtime_status.get("failed_count") or 0),
        "total_items": int(runtime_status.get("total_items") or 0),
        "progress": float(runtime_status.get("progress") or 0.0),
        "started_at": _parse_dt(runtime_status.get("started_at")),
        "finished_at": _parse_dt(runtime_status.get("finished_at")),
        "result_file_name": runtime_status.get("result_file_name"),
    }


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
        manual_job=_resolve_console_job_status(),
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


API_STAGE_MODULE_MAP: dict[str, str] = {
    "policy_tier1": "policy_intel",
    "policy_tier2": "policy_intel",
    "personnel_enrichment": "personnel_intel",
    "tech_frontier_topic": "tech_frontier",
    "tech_frontier_opportunity": "tech_frontier",
    "daily_briefing_generation": "daily_briefing",
    "paper_transfer": "paper_transfer",
    "crawler_scholar_fields": "crawler_scholar",
}

DEFAULT_SYSTEM_LABELS: dict[str, str] = {
    "deanagent-backend": "Crawler System",
    "nano-bot": "Nano Bot",
    "doc2brief": "Doc2Brief",
    "dean-agent-fronted": "Dean Agent Fronted",
}

PROJECT_SYSTEM_ALIASES: dict[str, str] = {
    "deanagent-backend": "deanagent-backend",
    "dean-nanobot": "nano-bot",
    "nanobot": "nano-bot",
    "file-to-weeklyreport": "doc2brief",
    "doc2brief": "doc2brief",
    "dean-agent-fronted": "dean-agent-fronted",
    "dean-agent-frontend": "dean-agent-fronted",
}

WORKSPACE_ROOT = BASE_DIR.parent
NANOBOT_USAGE_FILE = Path.home() / ".nanobot" / "usage.jsonl"
WORKSPACE_OPENROUTER_USAGE_PATTERNS: tuple[str, ...] = (
    "data/usage/openrouter-usage.ndjson",
    "logs/openrouter-usage.ndjson",
    "usage/openrouter-usage.ndjson",
)
WORKSPACE_CALLS_JSONL_PATTERNS: tuple[str, ...] = (
    "data/logs/llm_calls/calls.jsonl",
    "logs/llm_calls/calls.jsonl",
)
OPENROUTER_MODELS_API_URL = "https://openrouter.ai/api/v1/models"

_OPENROUTER_PRICING_CACHE: dict[str, tuple[float, float]] = {}
_OPENROUTER_PRICING_CACHE_EXPIRES_AT: datetime | None = None
_OPENROUTER_PRICING_TTL = timedelta(hours=6)


def _module_from_stage(stage: str) -> str:
    if stage.startswith("crawler_llm_faculty_"):
        return "crawler_faculty"
    return API_STAGE_MODULE_MAP.get(stage, "other")


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except ValueError:
            return 0
    return 0


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _normalize_model_name(raw_model: Any) -> str:
    model = str(raw_model or "").strip()
    if not model:
        return "unknown"
    if model.lower().startswith("openrouter/"):
        stripped = model.split("/", 1)[1].strip()
        return stripped or "unknown"
    return model


def _sanitize_system_key(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    return cleaned or "unknown"


def _humanize_system_label(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", str(value).strip()) if part]
    if not parts:
        return "Unknown System"
    return " ".join(part.capitalize() for part in parts)


def _resolve_system_identity(
    *,
    project_name: str | None = None,
    system_key: str | None = None,
) -> tuple[str, str]:
    if system_key:
        normalized = _sanitize_system_key(system_key)
        label = DEFAULT_SYSTEM_LABELS.get(normalized) or _humanize_system_label(system_key)
        return normalized, label

    normalized_project = _sanitize_system_key(project_name or "")
    normalized_system = PROJECT_SYSTEM_ALIASES.get(normalized_project, normalized_project)
    label = DEFAULT_SYSTEM_LABELS.get(normalized_system)
    if not label:
        label = _humanize_system_label(project_name or normalized_system)
    return normalized_system, label


def _normalize_system_key(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _sanitize_system_key(value)
    return cleaned or None


def _estimate_cost_from_pricing_map(model: str, input_tokens: int, output_tokens: int) -> float | None:
    pricing = PRICING_MAP.get(model)
    if not pricing:
        return None
    input_cost = (input_tokens / 1_000_000) * float(pricing.get("input", 0.0))
    output_cost = (output_tokens / 1_000_000) * float(pricing.get("output", 0.0))
    return input_cost + output_cost


def _extract_effective_cost(call: dict[str, Any]) -> tuple[float | None, str]:
    explicit_effective = _safe_float(call.get("effective_cost_usd"))
    explicit_source = str(call.get("cost_source") or "").strip()
    if explicit_effective is not None:
        return explicit_effective, explicit_source or "pricing_map"

    provider_cost = _safe_float(call.get("provider_cost_usd"))
    if provider_cost is not None:
        return provider_cost, "provider"

    legacy_cost = _safe_float(call.get("cost_usd"))
    if legacy_cost is not None and legacy_cost > 0:
        return legacy_cost, explicit_source or "legacy_recorded"

    model = _normalize_model_name(call.get("model"))
    input_tokens = _safe_int(call.get("input_tokens"))
    output_tokens = _safe_int(call.get("output_tokens"))
    estimated = _estimate_cost_from_pricing_map(model, input_tokens, output_tokens)
    if estimated is not None:
        return estimated, "pricing_map"

    if explicit_source:
        return None, explicit_source
    return None, "unpriced"


def _parse_ts_millis(value: Any) -> datetime | None:
    as_float = _safe_float(value)
    if as_float is None or as_float <= 0:
        return None
    seconds = as_float / 1000 if as_float > 100_000_000_000 else as_float
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def _iter_json_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    rows.append(parsed)
    except OSError:
        return []

    return rows


def _load_llm_calls() -> list[dict[str, Any]]:
    return _iter_json_records(CALLS_LOG_FILE)


def _load_backend_api_rows(*, since: datetime) -> list[dict[str, Any]]:
    backend_system, backend_label = _resolve_system_identity(system_key="deanagent-backend")
    rows: list[dict[str, Any]] = []
    for raw in _load_llm_calls():
        ts = _parse_dt(raw.get("timestamp"))
        if ts is None or ts < since:
            continue

        provider = str(raw.get("provider") or "openrouter").strip().lower()
        if provider != "openrouter":
            continue

        stage_value = str(raw.get("stage") or "unknown")
        module_value = _module_from_stage(stage_value)
        model_value = _normalize_model_name(raw.get("model"))
        source_value = str(raw.get("source_id") or "").strip() or None
        success_value = bool(raw.get("success", False))

        input_tokens = max(_safe_int(raw.get("input_tokens")), 0)
        output_tokens = max(_safe_int(raw.get("output_tokens")), 0)
        total_tokens = max(_safe_int(raw.get("total_tokens")), 0)
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens

        effective_cost, cost_source = _extract_effective_cost(raw)

        rows.append(
            {
                "timestamp": ts,
                "provider": provider,
                "system": backend_system,
                "system_label": backend_label,
                "module": module_value,
                "stage": stage_value,
                "model": model_value,
                "source_id": source_value,
                "article_id": (str(raw.get("article_id")).strip() if raw.get("article_id") else None),
                "article_title": (
                    str(raw.get("article_title")).strip() if raw.get("article_title") else None
                ),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "effective_cost_usd": effective_cost,
                "cost_source": cost_source,
                "success": success_value,
                "duration_ms": _safe_float(raw.get("duration_ms")),
            }
        )

    return rows


def _load_nanobot_api_rows(
    *,
    since: datetime,
    path: Path = NANOBOT_USAGE_FILE,
    system: str = "nano-bot",
    system_label: str | None = None,
    module: str = "nano_bot",
    stage: str = "nanobot_chat",
) -> list[dict[str, Any]]:
    resolved_system, resolved_label = _resolve_system_identity(system_key=system)
    label = system_label or resolved_label

    rows: list[dict[str, Any]] = []
    for raw in _iter_json_records(path):
        ts = _parse_dt(raw.get("ts")) or _parse_ts_millis(raw.get("ts"))
        if ts is None or ts < since:
            continue

        model_value = _normalize_model_name(raw.get("model"))
        input_tokens = max(_safe_int(raw.get("in")), 0)
        output_tokens = max(_safe_int(raw.get("out")), 0)
        total_tokens = max(_safe_int(raw.get("total")), 0)
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens

        raw_cost = _safe_float(raw.get("cost"))
        effective_cost = raw_cost if raw_cost is not None and raw_cost >= 0 else None
        source_id = str(raw.get("channel") or "").strip() or str(raw.get("sender") or "").strip() or None

        rows.append(
            {
                "timestamp": ts,
                "provider": "openrouter",
                "system": resolved_system,
                "system_label": label,
                "module": module,
                "stage": stage,
                "model": model_value,
                "source_id": source_id,
                "article_id": None,
                "article_title": None,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "effective_cost_usd": effective_cost,
                "cost_source": "recorded" if effective_cost is not None else "unpriced",
                "success": True,
                "duration_ms": None,
            }
        )

    return rows


def _load_doc2brief_usage_rows(
    path: Path,
    *,
    since: datetime,
    system: str,
    system_label: str,
    module: str,
    stage: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in _iter_json_records(path):
        ts = _parse_dt(raw.get("createdAt")) or _parse_ts_millis(raw.get("ts"))
        if ts is None or ts < since:
            continue

        model_value = _normalize_model_name(raw.get("model"))
        input_tokens = max(_safe_int(raw.get("promptTokens")), 0)
        output_tokens = max(_safe_int(raw.get("completionTokens")), 0)
        total_tokens = max(_safe_int(raw.get("totalTokens")), 0)
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens

        status_code = _safe_int(raw.get("statusCode"))
        error_message = str(raw.get("error") or "").strip()
        success = 200 <= status_code < 400 and not error_message

        raw_cost = _safe_float(raw.get("costUsd"))
        raw_cost_source = str(raw.get("costSource") or "").strip().lower()
        if raw_cost is not None and (raw_cost > 0 or raw_cost_source in {"provider", "estimated", "recorded"}):
            effective_cost = raw_cost
            cost_source = raw_cost_source or "recorded"
        else:
            effective_cost = None
            cost_source = "unpriced" if raw_cost_source in {"", "unavailable"} else raw_cost_source

        source_value = str(raw.get("id") or "").strip() or None
        article_title = (
            str(raw.get("error") or "").strip() if (not success and raw.get("error")) else None
        )

        rows.append(
            {
                "timestamp": ts,
                "provider": "openrouter",
                "system": system,
                "system_label": system_label,
                "module": module,
                "stage": stage,
                "model": model_value,
                "source_id": source_value,
                "article_id": source_value,
                "article_title": article_title,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "effective_cost_usd": effective_cost,
                "cost_source": cost_source,
                "success": success,
                "duration_ms": _safe_float(raw.get("durationMs")),
            }
        )

    return rows


def _load_calls_jsonl_rows(
    path: Path,
    *,
    since: datetime,
    system: str,
    system_label: str,
    module_hint: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in _iter_json_records(path):
        ts = _parse_dt(raw.get("timestamp"))
        if ts is None or ts < since:
            continue

        provider = str(raw.get("provider") or "openrouter").strip().lower()
        if provider != "openrouter":
            continue

        stage_value = str(raw.get("stage") or "unknown")
        module_value = _module_from_stage(stage_value)
        if module_value == "other":
            module_value = module_hint

        model_value = _normalize_model_name(raw.get("model"))
        source_value = str(raw.get("source_id") or "").strip() or None
        success_value = bool(raw.get("success", False))

        input_tokens = max(_safe_int(raw.get("input_tokens")), 0)
        output_tokens = max(_safe_int(raw.get("output_tokens")), 0)
        total_tokens = max(_safe_int(raw.get("total_tokens")), 0)
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens

        effective_cost, cost_source = _extract_effective_cost(raw)

        rows.append(
            {
                "timestamp": ts,
                "provider": provider,
                "system": system,
                "system_label": system_label,
                "module": module_value,
                "stage": stage_value,
                "model": model_value,
                "source_id": source_value,
                "article_id": (str(raw.get("article_id")).strip() if raw.get("article_id") else None),
                "article_title": (
                    str(raw.get("article_title")).strip() if raw.get("article_title") else None
                ),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "effective_cost_usd": effective_cost,
                "cost_source": cost_source,
                "success": success_value,
                "duration_ms": _safe_float(raw.get("duration_ms")),
            }
        )

    return rows


def _workspace_project_name(path: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(WORKSPACE_ROOT.resolve())
    except ValueError:
        return None

    if not relative.parts:
        return None
    return relative.parts[0]


def _discover_workspace_project_files(patterns: tuple[str, ...]) -> list[Path]:
    selected: dict[str, Path] = {}

    for pattern in patterns:
        for path in sorted(WORKSPACE_ROOT.glob(f"*/{pattern}")):
            if not path.is_file():
                continue
            project = _workspace_project_name(path)
            if not project:
                continue
            if project in selected:
                continue
            selected[project] = path

    return [selected[project] for project in sorted(selected)]


def _discover_workspace_api_sources() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    def append_source(source: dict[str, Any]) -> None:
        candidate_path = source["path"]
        try:
            normalized_path = str(Path(candidate_path).resolve())
        except OSError:
            normalized_path = str(candidate_path)
        if normalized_path in seen_paths:
            return
        seen_paths.add(normalized_path)
        sources.append(source)

    if NANOBOT_USAGE_FILE.is_file():
        system, label = _resolve_system_identity(system_key="nano-bot")
        append_source(
            {
                "kind": "nanobot_usage_jsonl",
                "path": NANOBOT_USAGE_FILE,
                "system": system,
                "system_label": label,
                "module": "nano_bot",
                "stage": "nanobot_chat",
            }
        )

    for path in _discover_workspace_project_files(WORKSPACE_OPENROUTER_USAGE_PATTERNS):
        project = _workspace_project_name(path)
        system, label = _resolve_system_identity(project_name=project)
        module = system.replace("-", "_")
        append_source(
            {
                "kind": "openrouter_usage_ndjson",
                "path": path,
                "system": system,
                "system_label": label,
                "module": module,
                "stage": f"{module}_openrouter_proxy",
            }
        )

    backend_log_path = str(CALLS_LOG_FILE.resolve())
    for path in _discover_workspace_project_files(WORKSPACE_CALLS_JSONL_PATTERNS):
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        if resolved == backend_log_path:
            continue

        project = _workspace_project_name(path)
        system, label = _resolve_system_identity(project_name=project)
        append_source(
            {
                "kind": "calls_jsonl",
                "path": path,
                "system": system,
                "system_label": label,
                "module": system.replace("-", "_"),
                "stage": "unknown",
            }
        )

    return sources


def _load_workspace_api_rows(*, since: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for source in _discover_workspace_api_sources():
        kind = str(source.get("kind") or "")
        path = Path(source["path"])
        system = str(source.get("system") or "unknown")
        system_label = str(source.get("system_label") or _humanize_system_label(system))
        module = str(source.get("module") or system.replace("-", "_"))
        stage = str(source.get("stage") or f"{module}_openrouter_proxy")

        if kind == "nanobot_usage_jsonl":
            rows.extend(
                _load_nanobot_api_rows(
                    since=since,
                    path=path,
                    system=system,
                    system_label=system_label,
                    module=module,
                    stage=stage,
                )
            )
            continue

        if kind == "openrouter_usage_ndjson":
            rows.extend(
                _load_doc2brief_usage_rows(
                    path,
                    since=since,
                    system=system,
                    system_label=system_label,
                    module=module,
                    stage=stage,
                )
            )
            continue

        if kind == "calls_jsonl":
            rows.extend(
                _load_calls_jsonl_rows(
                    path,
                    since=since,
                    system=system,
                    system_label=system_label,
                    module_hint=module,
                )
            )

    return rows


async def _fetch_openrouter_pricing_map() -> dict[str, tuple[float, float]]:
    global _OPENROUTER_PRICING_CACHE_EXPIRES_AT, _OPENROUTER_PRICING_CACHE

    now = datetime.now(timezone.utc)
    if _OPENROUTER_PRICING_CACHE and _OPENROUTER_PRICING_CACHE_EXPIRES_AT and now < _OPENROUTER_PRICING_CACHE_EXPIRES_AT:
        return _OPENROUTER_PRICING_CACHE

    parsed: dict[str, tuple[float, float]] = {}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(OPENROUTER_MODELS_API_URL)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        # Keep fail-open behavior for console; unknown models remain unpriced.
        _OPENROUTER_PRICING_CACHE_EXPIRES_AT = now + timedelta(minutes=10)
        return _OPENROUTER_PRICING_CACHE

    items = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            model_name = _normalize_model_name(item.get("id"))
            if model_name == "unknown":
                continue
            pricing = item.get("pricing")
            if not isinstance(pricing, dict):
                continue
            prompt_price = _safe_float(pricing.get("prompt"))
            completion_price = _safe_float(pricing.get("completion"))
            if prompt_price is None or completion_price is None:
                continue
            if prompt_price < 0 or completion_price < 0:
                continue
            parsed[model_name.lower()] = (prompt_price, completion_price)

    _OPENROUTER_PRICING_CACHE = parsed
    _OPENROUTER_PRICING_CACHE_EXPIRES_AT = now + _OPENROUTER_PRICING_TTL
    return _OPENROUTER_PRICING_CACHE


async def _apply_openrouter_dynamic_pricing(rows: list[dict[str, Any]]) -> None:
    missing_models = {
        str(row.get("model") or "").lower()
        for row in rows
        if row.get("effective_cost_usd") is None
        and str(row.get("provider") or "").lower() == "openrouter"
        and str(row.get("model") or "")
        and not str(row.get("model") or "").startswith("unknown/")
    }
    if not missing_models:
        return

    pricing_map = await _fetch_openrouter_pricing_map()
    if not pricing_map:
        return

    for row in rows:
        if row.get("effective_cost_usd") is not None:
            continue
        model_key = str(row.get("model") or "").lower()
        pricing = pricing_map.get(model_key)
        if not pricing:
            continue
        prompt_price, completion_price = pricing
        estimated = (
            max(_safe_int(row.get("input_tokens")), 0) * prompt_price
            + max(_safe_int(row.get("output_tokens")), 0) * completion_price
        )
        row["effective_cost_usd"] = max(estimated, 0.0)
        row["cost_source"] = "openrouter_models_api"


def _init_usage_bucket() -> dict[str, Any]:
    return {
        "call_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "priced_calls": 0,
        "unpriced_calls": 0,
    }


def _build_api_trend_series(
    *,
    rows: list[dict[str, Any]],
    days: int,
    systems: list[str],
    system_label_map: dict[str, str | None] | None = None,
) -> list[dict[str, Any]]:
    start_day = _now_local_day() - timedelta(days=days - 1)
    day_keys = [start_day + timedelta(days=offset) for offset in range(days)]

    trend_map: dict[str, dict[date, dict[str, Any]]] = {}
    for system in systems:
        trend_map[system] = {
            day_key: {
                "call_count": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
            }
            for day_key in day_keys
        }

    for row in rows:
        system = str(row.get("system") or "")
        if system not in trend_map:
            continue
        ts = row.get("timestamp")
        if not isinstance(ts, datetime):
            continue
        day_key = ts.astimezone(CONSOLE_TIMEZONE).date()
        if day_key not in trend_map[system]:
            continue

        bucket = trend_map[system][day_key]
        bucket["call_count"] += 1
        bucket["total_tokens"] += max(_safe_int(row.get("total_tokens")), 0)
        if row.get("effective_cost_usd") is not None:
            bucket["total_cost_usd"] += float(row["effective_cost_usd"])

    labels = system_label_map or {}
    series: list[dict[str, Any]] = []
    for system in systems:
        points = [
            {
                "date": day_key,
                "call_count": trend_map[system][day_key]["call_count"],
                "total_tokens": trend_map[system][day_key]["total_tokens"],
                "total_cost_usd": round(trend_map[system][day_key]["total_cost_usd"], 6),
            }
            for day_key in day_keys
        ]
        series.append(
            {
                "system": system,
                "system_label": labels.get(system),
                "points": points,
            }
        )

    return series


async def get_console_api_usage(
    *,
    days: int = 7,
    system: str | None = None,
    module: str | None = None,
    stage: str | None = None,
    model: str | None = None,
    source_id: str | None = None,
    success: str = "all",
    limit: int = 80,
) -> ConsoleApiUsageResponse:
    safe_days = max(1, min(int(days), 30))
    safe_limit = max(1, min(int(limit), 200))
    success_mode = success if success in {"all", "success", "failed"} else "all"
    system_mode = _normalize_system_key(system)

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=safe_days)

    workspace_sources = _discover_workspace_api_sources()

    base_rows = _load_backend_api_rows(since=since)
    base_rows.extend(_load_workspace_api_rows(since=since))

    available_modules: set[str] = set()
    available_stages: set[str] = set()
    available_models: set[str] = set()
    available_source_ids: set[str] = set()

    backend_key, backend_label = _resolve_system_identity(system_key="deanagent-backend")
    system_label_map: dict[str, str | None] = {backend_key: backend_label}

    for source in workspace_sources:
        source_system = str(source.get("system") or "").strip()
        if not source_system:
            continue
        source_label = str(source.get("system_label") or "").strip()
        if source_label:
            system_label_map[source_system] = source_label
        elif source_system not in system_label_map:
            system_label_map[source_system] = (
                DEFAULT_SYSTEM_LABELS.get(source_system) or _humanize_system_label(source_system)
            )

    for row in base_rows:
        available_modules.add(str(row.get("module") or "unknown"))
        available_stages.add(str(row.get("stage") or "unknown"))
        available_models.add(str(row.get("model") or "unknown"))

        source_value = str(row.get("source_id") or "").strip()
        if source_value:
            available_source_ids.add(source_value)

        row_system = str(row.get("system") or "").strip()
        if row_system:
            row_label = str(row.get("system_label") or "").strip()
            if row_label:
                system_label_map[row_system] = row_label
            elif row_system not in system_label_map:
                system_label_map[row_system] = (
                    DEFAULT_SYSTEM_LABELS.get(row_system) or _humanize_system_label(row_system)
                )

    filtered_rows: list[dict[str, Any]] = []
    for row in base_rows:
        if system_mode and row["system"] != system_mode:
            continue
        if module and row["module"] != module:
            continue
        if stage and row["stage"] != stage:
            continue
        if model and row["model"] != model:
            continue
        if source_id and row["source_id"] != source_id:
            continue
        if success_mode == "success" and not row["success"]:
            continue
        if success_mode == "failed" and row["success"]:
            continue
        filtered_rows.append(row)

    await _apply_openrouter_dynamic_pricing(filtered_rows)

    filtered_rows.sort(key=lambda item: item["timestamp"], reverse=True)

    if system_mode:
        if system_mode not in system_label_map:
            system_label_map[system_mode] = (
                DEFAULT_SYSTEM_LABELS.get(system_mode) or _humanize_system_label(system_mode)
            )
        systems_in_scope = [system_mode]
    else:
        systems_in_scope = sorted(system_label_map)

    overview = _init_usage_bucket()
    by_system_map: dict[str, dict[str, Any]] = {
        key: {
            "system": key,
            "system_label": system_label_map.get(key),
            **_init_usage_bucket(),
        }
        for key in systems_in_scope
    }
    by_module_map: dict[str, dict[str, Any]] = {}
    by_model_map: dict[str, dict[str, Any]] = {}
    by_stage_map: dict[str, dict[str, Any]] = {}

    for row in filtered_rows:
        overview["call_count"] += 1
        overview["success_count"] += 1 if row["success"] else 0
        overview["failed_count"] += 0 if row["success"] else 1
        overview["input_tokens"] += row["input_tokens"]
        overview["output_tokens"] += row["output_tokens"]
        overview["total_tokens"] += row["total_tokens"]

        if row["effective_cost_usd"] is None:
            overview["unpriced_calls"] += 1
        else:
            overview["priced_calls"] += 1
            overview["total_cost_usd"] += row["effective_cost_usd"]

        system_bucket = by_system_map.setdefault(
            row["system"],
            {
                "system": row["system"],
                "system_label": (
                    row.get("system_label")
                    or system_label_map.get(row["system"])
                    or DEFAULT_SYSTEM_LABELS.get(row["system"])
                ),
                **_init_usage_bucket(),
            },
        )
        mod_bucket = by_module_map.setdefault(row["module"], {"module": row["module"], **_init_usage_bucket()})
        model_bucket = by_model_map.setdefault(row["model"], {"model": row["model"], **_init_usage_bucket()})
        stage_bucket = by_stage_map.setdefault(
            row["stage"], {"stage": row["stage"], "module": row["module"], **_init_usage_bucket()}
        )

        for bucket in (system_bucket, mod_bucket, model_bucket, stage_bucket):
            bucket["call_count"] += 1
            bucket["success_count"] += 1 if row["success"] else 0
            bucket["failed_count"] += 0 if row["success"] else 1
            bucket["input_tokens"] += row["input_tokens"]
            bucket["output_tokens"] += row["output_tokens"]
            bucket["total_tokens"] += row["total_tokens"]
            if row["effective_cost_usd"] is None:
                bucket["unpriced_calls"] += 1
            else:
                bucket["priced_calls"] += 1
                bucket["total_cost_usd"] += row["effective_cost_usd"]

    success_rate = (
        round((overview["success_count"] / overview["call_count"]) * 100, 2)
        if overview["call_count"]
        else 0.0
    )
    avg_cost_per_call = (
        round(overview["total_cost_usd"] / overview["priced_calls"], 6)
        if overview["priced_calls"]
        else 0.0
    )

    overview_model = ConsoleApiUsageOverview(
        total_calls=overview["call_count"],
        success_calls=overview["success_count"],
        failed_calls=overview["failed_count"],
        success_rate=success_rate,
        total_input_tokens=overview["input_tokens"],
        total_output_tokens=overview["output_tokens"],
        total_tokens=overview["total_tokens"],
        total_cost_usd=round(overview["total_cost_usd"], 6),
        priced_calls=overview["priced_calls"],
        unpriced_calls=overview["unpriced_calls"],
        unpriced_tokens=sum(
            row["total_tokens"] for row in filtered_rows if row["effective_cost_usd"] is None
        ),
        avg_cost_per_call_usd=avg_cost_per_call,
    )

    by_system = [
        {
            "system": item["system"],
            "system_label": (
                item.get("system_label")
                or system_label_map.get(item["system"])
                or DEFAULT_SYSTEM_LABELS.get(item["system"])
            ),
            "call_count": item["call_count"],
            "success_count": item["success_count"],
            "failed_count": item["failed_count"],
            "success_rate": (
                round((item["success_count"] / item["call_count"]) * 100, 2)
                if item["call_count"]
                else 0.0
            ),
            "input_tokens": item["input_tokens"],
            "output_tokens": item["output_tokens"],
            "total_tokens": item["total_tokens"],
            "total_cost_usd": round(item["total_cost_usd"], 6),
            "priced_calls": item["priced_calls"],
            "unpriced_calls": item["unpriced_calls"],
        }
        for item in sorted(
            by_system_map.values(),
            key=lambda x: (-x["total_cost_usd"], -x["total_tokens"], -x["call_count"], x["system"]),
        )
    ]

    by_module = [
        ConsoleApiUsageModuleItem(
            module=item["module"],
            call_count=item["call_count"],
            success_count=item["success_count"],
            failed_count=item["failed_count"],
            input_tokens=item["input_tokens"],
            output_tokens=item["output_tokens"],
            total_tokens=item["total_tokens"],
            total_cost_usd=round(item["total_cost_usd"], 6),
            priced_calls=item["priced_calls"],
            unpriced_calls=item["unpriced_calls"],
        )
        for item in sorted(
            by_module_map.values(),
            key=lambda x: (-x["total_cost_usd"], -x["total_tokens"], -x["call_count"], x["module"]),
        )
    ]

    by_model = [
        ConsoleApiUsageModelItem(
            model=item["model"],
            call_count=item["call_count"],
            success_count=item["success_count"],
            failed_count=item["failed_count"],
            input_tokens=item["input_tokens"],
            output_tokens=item["output_tokens"],
            total_tokens=item["total_tokens"],
            total_cost_usd=round(item["total_cost_usd"], 6),
            priced_calls=item["priced_calls"],
            unpriced_calls=item["unpriced_calls"],
            avg_cost_per_call_usd=(
                round(item["total_cost_usd"] / item["priced_calls"], 6) if item["priced_calls"] else 0.0
            ),
        )
        for item in sorted(
            by_model_map.values(),
            key=lambda x: (-x["total_cost_usd"], -x["total_tokens"], -x["call_count"], x["model"]),
        )
    ]

    by_stage = [
        ConsoleApiUsageStageItem(
            stage=item["stage"],
            module=item["module"],
            call_count=item["call_count"],
            success_count=item["success_count"],
            failed_count=item["failed_count"],
            input_tokens=item["input_tokens"],
            output_tokens=item["output_tokens"],
            total_tokens=item["total_tokens"],
            total_cost_usd=round(item["total_cost_usd"], 6),
            priced_calls=item["priced_calls"],
            unpriced_calls=item["unpriced_calls"],
        )
        for item in sorted(
            by_stage_map.values(),
            key=lambda x: (-x["total_cost_usd"], -x["total_tokens"], -x["call_count"], x["stage"]),
        )
    ]

    trend_series = _build_api_trend_series(
        rows=filtered_rows,
        days=safe_days,
        systems=[item["system"] for item in by_system],
        system_label_map=system_label_map,
    )

    recent_calls = [
        ConsoleApiRecentCall(
            timestamp=row["timestamp"],
            provider=row["provider"],
            system=row["system"],
            system_label=(
                row.get("system_label")
                or system_label_map.get(row["system"])
                or DEFAULT_SYSTEM_LABELS.get(row["system"])
            ),
            module=row["module"],
            stage=row["stage"],
            model=row["model"],
            source_id=row["source_id"],
            article_id=row["article_id"],
            article_title=row["article_title"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            total_tokens=row["total_tokens"],
            effective_cost_usd=row["effective_cost_usd"],
            cost_source=row["cost_source"],
            success=row["success"],
            duration_ms=row["duration_ms"],
        )
        for row in filtered_rows[:safe_limit]
    ]

    return ConsoleApiUsageResponse(
        generated_at=now,
        scope=ConsoleApiUsageScope(
            provider="openrouter",
            days=safe_days,
            system=system_mode,
            module=module,
            stage=stage,
            model=model,
            source_id=source_id,
            success=success_mode,
            limit=safe_limit,
        ),
        overview=overview_model,
        by_system=by_system,
        by_module=by_module,
        by_model=by_model,
        by_stage=by_stage,
        trend_series=trend_series,
        recent_calls=recent_calls,
        available_filters=ConsoleApiUsageAvailableFilters(
            modules=sorted(available_modules),
            stages=sorted(available_stages),
            models=sorted(available_models),
            source_ids=sorted(available_source_ids),
            systems=sorted(system_label_map.keys()),
        ),
    )
