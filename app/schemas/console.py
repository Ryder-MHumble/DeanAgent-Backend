from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.crawl_log import CrawlHealthResponse, CrawlLogResponse


class CrawlRequest(BaseModel):
    """Request to start a manual crawl job."""

    source_ids: list[str]
    keyword_filter: list[str] | None = None
    keyword_blacklist: list[str] | None = None
    export_format: Literal["json", "csv", "database"] = "json"


class CrawlStatusResponse(BaseModel):
    """Current manual crawl job status."""

    is_running: bool
    current_source: str | None = None
    completed_sources: list[str] = Field(default_factory=list)
    failed_sources: list[str] = Field(default_factory=list)
    requested_source_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    total_items: int = 0
    running_sources: list[str] = Field(default_factory=list)
    recent_activity: list[CrawlActivityEntry] = Field(default_factory=list)
    summary_report: CrawlSummaryReport | None = None
    progress: float = 0.0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_file_name: str | None = None


class CrawlStartResponse(BaseModel):
    """Manual crawl start acknowledgement."""

    status: str
    requested_source_count: int
    accepted_source_count: int
    rejected_source_ids: list[str] = Field(default_factory=list)


class CrawlJobResponse(BaseModel):
    """Manual crawl job payload."""

    job_id: str
    status: Literal["queued", "running", "cancelling", "completed", "failed", "cancelled"]
    source_ids: list[str] = Field(default_factory=list)
    requested_source_count: int = 0
    accepted_source_count: int = 0
    rejected_source_ids: list[str] = Field(default_factory=list)
    cancel_requested: bool = False
    current_source: str | None = None
    completed_sources: list[str] = Field(default_factory=list)
    failed_sources: list[str] = Field(default_factory=list)
    completed_count: int = 0
    failed_count: int = 0
    total_items: int = 0
    running_sources: list[str] = Field(default_factory=list)
    recent_activity: list[CrawlActivityEntry] = Field(default_factory=list)
    summary_report: CrawlSummaryReport | None = None
    progress: float = 0.0
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_file_name: str | None = None
    error_message: str | None = None


class ConsoleTodayStats(BaseModel):
    """Daily crawl summary for the console."""

    date: date
    timezone: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    no_new_content_runs: int
    unique_sources: int
    total_items: int
    new_items: int
    average_duration_seconds: float = 0.0
    last_run_at: datetime | None = None


class CrawlActivityEntry(BaseModel):
    """Per-source activity item for live crawl timeline."""

    timestamp: datetime
    source_id: str
    phase: str
    status: str
    message: str = ""
    items_total: int = 0
    db_upserted: int = 0
    db_new: int = 0
    db_deduped_in_batch: int = 0


class CrawlSummaryReport(BaseModel):
    """Manual crawl summary report (final or in-progress snapshot)."""

    requested_source_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    total_items: int = 0
    db_upserted_total: int = 0
    db_new_total: int = 0
    db_deduped_in_batch_total: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float = 0.0
    status: str = "idle"


class ConsoleDimensionSummary(BaseModel):
    """Per-dimension health and activity summary."""

    dimension: str
    dimension_name: str | None = None
    total_sources: int
    enabled_sources: int
    healthy_sources: int
    warning_sources: int
    failing_sources: int
    today_runs: int
    today_new_items: int
    last_run_at: datetime | None = None


class ConsoleRecentRun(BaseModel):
    """Recent crawl execution item for the console timeline."""

    source_id: str
    source_name: str | None = None
    dimension: str | None = None
    dimension_name: str | None = None
    status: str
    items_total: int = 0
    items_new: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None


class ConsoleDailyTrendPoint(BaseModel):
    """Daily trend point for chart rendering."""

    date: date
    crawls: int
    success: int
    failed: int
    no_new_content: int
    new_items: int
    total_items: int


class ConsoleServerMetrics(BaseModel):
    """Server health metrics for the crawler console."""

    cpu_percent: float
    memory_percent: float
    disk_percent: float
    load_average_1m: float
    cpu_count: int
    uptime_seconds: int
    sampled_at: datetime


class ConsoleOverviewResponse(BaseModel):
    """Top-level crawler console overview payload."""

    generated_at: datetime
    scheduler_status: Literal["running", "not_started"]
    health: CrawlHealthResponse
    today: ConsoleTodayStats
    manual_job: CrawlStatusResponse
    dimension_stats: list[ConsoleDimensionSummary] = Field(default_factory=list)
    recent_runs: list[ConsoleRecentRun] = Field(default_factory=list)


class ConsoleSourceLogsResponse(BaseModel):
    """Source detail logs payload."""

    source_id: str
    logs: list[CrawlLogResponse] = Field(default_factory=list)
