"""Service for controlling crawler execution from frontend UI."""
from __future__ import annotations

import asyncio
import contextlib
import csv
import dataclasses
import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import yaml

from app.config import BASE_DIR
from app.crawlers.base import CrawlStatus
from app.crawlers.registry import create_crawler
from app.crawlers.utils.json_storage import save_crawl_result_json
from app.scheduler.manager import load_all_source_configs
from app.services.stores.crawl_log_store import append_crawl_log
from app.services.stores.source_state import update_source_state
from app.services.talent_scout import export_talent_scout_workbook

logger = logging.getLogger(__name__)
MAX_ACTIVITY_ENTRIES = 200

class CrawlJobValidationError(ValueError):
    """Invalid manual crawl job request."""


class CrawlJobNotFoundError(KeyError):
    """Manual crawl job not found."""


class CrawlJobStateError(RuntimeError):
    """Manual crawl job state does not allow the requested operation."""


class CrawlerControlService:
    """Service for managing manual crawler execution."""

    def __init__(self):
        self._jobs: dict[str, dict[str, Any]] = {}
        self._latest_job_id: str | None = None
        self._running_job_id: str | None = None

    def is_running(self) -> bool:
        """Check if a crawl job is currently running."""
        return self._running_job_id is not None

    def get_status(self) -> dict[str, Any]:
        """Get latest crawl job status for compatibility endpoints."""
        job = self._get_latest_job()
        if job is None:
            return self._empty_status()
        return self._job_to_legacy_status(job)

    def stop_crawl(self):
        """Request to stop the current crawl job."""
        running_job = self._get_running_job()
        if running_job is None:
            return
        self._request_cancel(running_job)

    def get_result_file(self) -> Path | None:
        """Get the path to the latest result file.

        Falls back to the most recent file in the exports directory
        if the in-memory reference was lost (e.g. after a server restart).
        """
        latest_job = self._get_latest_job()
        if latest_job is not None:
            file_path = latest_job.get("result_file")
            if isinstance(file_path, Path) and file_path.exists():
                return file_path

        exports_dir = BASE_DIR / "data" / "exports"
        if not exports_dir.exists():
            return None

        candidates = sorted(
            exports_dir.glob("crawl_results_*.*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def create_job(
        self,
        *,
        source_ids: list[str],
        keyword_filter: list[str] | None = None,
        keyword_blacklist: list[str] | None = None,
        export_format: Literal["json", "csv", "database", "xlsx"] = "json",
    ) -> dict[str, Any]:
        """Create and start a manual crawl job."""
        if self.is_running():
            raise CrawlJobStateError("A crawl job is already running")
        if not source_ids:
            raise CrawlJobValidationError("source_ids cannot be empty")

        accepted_sources, rejected_sources = self.validate_source_ids(source_ids)
        if not accepted_sources:
            raise CrawlJobValidationError("No valid source IDs were provided")

        now = datetime.now(timezone.utc)
        job_id = uuid4().hex
        job = {
            "job_id": job_id,
            "status": "queued",
            "source_ids": accepted_sources,
            "requested_source_count": len(source_ids),
            "accepted_source_count": len(accepted_sources),
            "rejected_source_ids": rejected_sources,
            "keyword_filter": keyword_filter,
            "keyword_blacklist": keyword_blacklist,
            "export_format": export_format,
            "cancel_requested": False,
            "current_source": None,
            "completed_sources": [],
            "failed_sources": [],
            "requested_source_count_effective": len(accepted_sources),
            "total_items": 0,
            "db_upserted_total": 0,
            "db_new_total": 0,
            "db_deduped_in_batch_total": 0,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "result_file": None,
            "all_results": [],
            "source_runs": [],
            "running_sources": [],
            "recent_activity": [],
            "summary_report": None,
            "error_message": None,
            "task": None,
        }
        self._jobs[job_id] = job
        self._latest_job_id = job_id
        self._running_job_id = job_id

        job["task"] = asyncio.create_task(self._run_job(job_id))
        return self._serialize_job(job)

    def get_job(self, job_id: str) -> dict[str, Any]:
        """Return manual crawl job details."""
        return self._serialize_job(self._require_job(job_id))

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        """Cancel a queued or running crawl job."""
        job = self._require_job(job_id)
        if job["status"] not in {"queued", "running", "cancelling"}:
            raise CrawlJobStateError(
                f"Cannot cancel job in status '{job['status']}'"
            )
        self._request_cancel(job)
        return self._serialize_job(job)

    def get_job_result_file(self, job_id: str) -> Path | None:
        """Return the exported result file for a specific job."""
        job = self._require_job(job_id)
        file_path = job.get("result_file")
        if isinstance(file_path, Path) and file_path.exists():
            return file_path
        return None

    async def start_crawl(
        self,
        source_ids: list[str],
        keyword_filter: list[str] | None = None,
        keyword_blacklist: list[str] | None = None,
        export_format: Literal["json", "csv", "database", "xlsx"] = "json",
    ):
        """Compatibility wrapper around jobs resource."""
        self.create_job(
            source_ids=source_ids,
            keyword_filter=keyword_filter,
            keyword_blacklist=keyword_blacklist,
            export_format=export_format,
        )

    async def start_crawl_in_background(
        self,
        *,
        source_ids: list[str],
        keyword_filter: list[str] | None = None,
        keyword_blacklist: list[str] | None = None,
        export_format: Literal["json", "csv", "database", "xlsx"] = "json",
    ) -> dict[str, Any]:
        """Compatibility wrapper used by older endpoints."""
        return self.create_job(
            source_ids=source_ids,
            keyword_filter=keyword_filter,
            keyword_blacklist=keyword_blacklist,
            export_format=export_format,
        )

    def validate_source_ids(self, source_ids: list[str]) -> tuple[list[str], list[str]]:
        """Split incoming source IDs into accepted and rejected sets."""
        all_configs = load_all_source_configs()
        valid_ids = {str(cfg.get("id") or "").strip() for cfg in all_configs if cfg.get("id")}

        accepted: list[str] = []
        rejected: list[str] = []
        seen: set[str] = set()
        for raw_id in source_ids:
            source_id = str(raw_id or "").strip()
            if not source_id or source_id in seen:
                continue
            seen.add(source_id)
            if source_id in valid_ids:
                accepted.append(source_id)
            else:
                rejected.append(source_id)

        return accepted, rejected

    async def _run_job(self, job_id: str) -> None:
        """Execute an in-memory crawl job."""
        job = self._require_job(job_id)
        job["status"] = "running"
        job["started_at"] = datetime.now(timezone.utc)
        job["finished_at"] = None
        job["error_message"] = None

        logger.info(
            "Starting manual crawl job %s: %d sources, format=%s",
            job_id,
            len(job["source_ids"]),
            job["export_format"],
        )

        try:
            all_configs = load_all_source_configs()
            config_map = {cfg["id"]: cfg for cfg in all_configs}
            selected_configs = [
                deepcopy(config_map[sid]) for sid in job["source_ids"] if sid in config_map
            ]
            job["requested_source_count_effective"] = len(selected_configs)

            if not selected_configs:
                raise CrawlJobValidationError("No valid source configs found")

            for config in selected_configs:
                if job["keyword_filter"] is not None:
                    config["keyword_filter"] = job["keyword_filter"]
                if job["keyword_blacklist"] is not None:
                    config["keyword_blacklist"] = job["keyword_blacklist"]

            grouped_limits = _load_grouped_crawl_limits()
            running_sources: set[str] = set()
            state_lock = asyncio.Lock()
            semaphores = {
                method: asyncio.Semaphore(max(1, int(limit)))
                for method, limit in grouped_limits.items()
            }
            default_semaphore = asyncio.Semaphore(5)

            async def _run_single_config(config: dict[str, Any]) -> dict[str, Any]:
                source_id = str(config.get("id") or "")
                crawl_method = str(config.get("crawl_method") or "static")
                semaphore = semaphores.get(crawl_method, default_semaphore)

                async with semaphore:
                    if job["cancel_requested"]:
                        self._append_activity(
                            job,
                            source_id=source_id,
                            phase="cancelled",
                            status="cancelled",
                            message="任务取消，信源未执行",
                        )
                        return {
                            "source_id": source_id,
                            "status": "cancelled",
                            "items_total": 0,
                            "items_dict": [],
                            "skipped": True,
                        }

                    async with state_lock:
                        running_sources.add(source_id)
                        job["current_source"] = source_id
                        job["running_sources"] = sorted(running_sources)

                    self._append_activity(
                        job,
                        source_id=source_id,
                        phase="running",
                        status="running",
                        message="开始抓取",
                    )

                    try:
                        crawler = create_crawler(config)
                        result = await crawler.run()

                        items_dict = [dataclasses.asdict(item) for item in result.items]
                        db_upserted = 0
                        db_new = 0
                        db_deduped_in_batch = 0
                        if job["export_format"] in ("json", "csv"):
                            job["all_results"].extend(items_dict)

                        if job["export_format"] == "database":
                            db_stats = await save_crawl_result_json(result, config)
                            if db_stats:
                                db_upserted = int(db_stats.get("upserted", 0) or 0)
                                db_new = int(db_stats.get("new", 0) or 0)
                                db_deduped_in_batch = int(db_stats.get("deduped_in_batch", 0) or 0)
                                logger.info(
                                    "Job %s persisted source=%s upserted=%d new=%d dedup_batch=%d",
                                    job_id,
                                    source_id,
                                    db_upserted,
                                    db_new,
                                    db_deduped_in_batch,
                                )

                        await append_crawl_log(
                            source_id=source_id,
                            status=result.status.value,
                            items_total=result.items_total,
                            items_new=result.items_new,
                            error_message=result.error_message,
                            started_at=result.started_at,
                            finished_at=result.finished_at,
                            duration_seconds=result.duration_seconds,
                        )

                        finished = result.finished_at or datetime.now(timezone.utc)
                        if result.status in (CrawlStatus.SUCCESS, CrawlStatus.NO_NEW_CONTENT):
                            await update_source_state(
                                source_id,
                                last_crawl_at=finished,
                                last_success_at=finished,
                                reset_failures=True,
                            )
                        else:
                            await update_source_state(source_id, last_crawl_at=finished)

                        self._append_activity(
                            job,
                            source_id=source_id,
                            phase="finished",
                            status=result.status.value,
                            message=(
                                f"抓取完成: items={int(result.items_total or 0)} "
                                f"db_new={db_new} db_upserted={db_upserted}"
                            ),
                            items_total=int(result.items_total or 0),
                            db_upserted=db_upserted,
                            db_new=db_new,
                            db_deduped_in_batch=db_deduped_in_batch,
                        )

                        return {
                            "source_id": source_id,
                            "source_name": str(config.get("name") or source_id),
                            "status": result.status.value,
                            "items_total": int(result.items_total or 0),
                            "items_dict": items_dict,
                            "db_upserted": db_upserted,
                            "db_new": db_new,
                            "db_deduped_in_batch": db_deduped_in_batch,
                            "executed_at": finished,
                            "error_message": result.error_message,
                            "skipped": False,
                        }
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Failed to crawl %s in job %s: %s", source_id, job_id, exc)
                        now = datetime.now(timezone.utc)
                        await append_crawl_log(
                            source_id=source_id,
                            status=CrawlStatus.FAILED.value,
                            error_message=str(exc),
                            started_at=now,
                            finished_at=now,
                        )
                        await update_source_state(source_id, last_crawl_at=now)
                        self._append_activity(
                            job,
                            source_id=source_id,
                            phase="finished",
                            status=CrawlStatus.FAILED.value,
                            message=f"抓取失败: {exc}",
                            items_total=0,
                            db_upserted=0,
                            db_new=0,
                            db_deduped_in_batch=0,
                        )
                        return {
                            "source_id": source_id,
                            "source_name": str(config.get("name") or source_id),
                            "status": CrawlStatus.FAILED.value,
                            "items_total": 0,
                            "items_dict": [],
                            "db_upserted": 0,
                            "db_new": 0,
                            "db_deduped_in_batch": 0,
                            "executed_at": now,
                            "error_message": str(exc),
                            "skipped": False,
                        }
                    finally:
                        async with state_lock:
                            running_sources.discard(source_id)
                            job["current_source"] = next(iter(running_sources), None)
                            job["running_sources"] = sorted(running_sources)

            tasks = [asyncio.create_task(_run_single_config(config)) for config in selected_configs]
            cancel_dispatched = False
            for finished_task in asyncio.as_completed(tasks):
                if job["cancel_requested"] and not cancel_dispatched:
                    for pending in tasks:
                        if not pending.done():
                            pending.cancel()
                    cancel_dispatched = True

                with contextlib.suppress(asyncio.CancelledError):
                    outcome = await finished_task
                    if outcome.get("skipped"):
                        continue
                    status = str(outcome.get("status") or "")
                    source_id = str(outcome.get("source_id") or "")
                    job["source_runs"].append(outcome)
                    if status in (CrawlStatus.SUCCESS.value, CrawlStatus.NO_NEW_CONTENT.value):
                        job["completed_sources"].append(source_id)
                    else:
                        job["failed_sources"].append(source_id)
                    job["total_items"] += int(outcome.get("items_total") or 0)
                    job["db_upserted_total"] += int(outcome.get("db_upserted") or 0)
                    job["db_new_total"] += int(outcome.get("db_new") or 0)
                    job["db_deduped_in_batch_total"] += int(
                        outcome.get("db_deduped_in_batch") or 0
                    )

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            if job["export_format"] in ("json", "csv") and job["all_results"]:
                job["result_file"] = await self._export_results(
                    job["all_results"],
                    job["export_format"],
                )
                logger.info("Results for job %s exported to %s", job_id, job["result_file"])
            elif job["export_format"] == "xlsx":
                output_dir = BASE_DIR / "data" / "exports"
                job["result_file"] = export_talent_scout_workbook(
                    source_configs=selected_configs,
                    source_runs=job["source_runs"],
                    output_dir=output_dir,
                    generated_at=job.get("finished_at") or datetime.now(timezone.utc),
                )
                logger.info("Results for job %s exported to %s", job_id, job["result_file"])

            if job["cancel_requested"]:
                job["status"] = "cancelled"
            else:
                job["status"] = "completed"
        except Exception as exc:  # noqa: BLE001
            logger.exception("Manual crawl job %s failed", job_id)
            job["status"] = "failed"
            job["error_message"] = str(exc)
        finally:
            job["current_source"] = None
            job["running_sources"] = []
            job["finished_at"] = datetime.now(timezone.utc)
            if self._running_job_id == job_id:
                self._running_job_id = None
            job["summary_report"] = self._build_summary_report(job)
            logger.info(
                "Crawl job %s finished: status=%s, %d completed, %d failed, %d total items",
                job_id,
                job["status"],
                len(job["completed_sources"]),
                len(job["failed_sources"]),
                job["total_items"],
            )

    async def _export_results(
        self,
        results: list[dict[str, Any]],
        format: Literal["json", "csv"],
    ) -> Path:
        """Export crawl results to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = BASE_DIR / "data" / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)

        def _json_default(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        if format == "json":
            file_path = output_dir / f"crawl_results_{timestamp}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2, default=_json_default)
            return file_path

        file_path = output_dir / f"crawl_results_{timestamp}.csv"
        if results:
            all_keys = set()
            for item in results:
                all_keys.update(item.keys())
            fieldnames = sorted(all_keys)

            with open(file_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)
        return file_path

    def _empty_status(self) -> dict[str, Any]:
        return {
            "is_running": False,
            "current_source": None,
            "completed_sources": [],
            "failed_sources": [],
            "requested_source_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "total_items": 0,
            "running_sources": [],
            "recent_activity": [],
            "summary_report": None,
            "progress": 0.0,
            "started_at": None,
            "finished_at": None,
            "result_file_name": None,
        }

    def _get_latest_job(self) -> dict[str, Any] | None:
        if self._latest_job_id is None:
            return None
        return self._jobs.get(self._latest_job_id)

    def _get_running_job(self) -> dict[str, Any] | None:
        if self._running_job_id is None:
            return None
        return self._jobs.get(self._running_job_id)

    def _require_job(self, job_id: str) -> dict[str, Any]:
        job = self._jobs.get(job_id)
        if job is None:
            raise CrawlJobNotFoundError(job_id)
        return job

    def _request_cancel(self, job: dict[str, Any]) -> None:
        job["cancel_requested"] = True
        if job["status"] in {"queued", "running"}:
            job["status"] = "cancelling"
        logger.info("Crawl job %s cancel requested", job["job_id"])

    def _job_progress(self, job: dict[str, Any]) -> float:
        total = int(job.get("requested_source_count_effective") or 0)
        if total <= 0:
            total = len(job["completed_sources"]) + len(job["failed_sources"])
            if job.get("current_source"):
                total += 1
        if total <= 0:
            return 0.0
        return (len(job["completed_sources"]) + len(job["failed_sources"])) / total

    def _serialize_job(self, job: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": job["job_id"],
            "status": job["status"],
            "source_ids": list(job["source_ids"]),
            "requested_source_count": job["requested_source_count"],
            "accepted_source_count": job["accepted_source_count"],
            "rejected_source_ids": list(job["rejected_source_ids"]),
            "cancel_requested": bool(job["cancel_requested"]),
            "current_source": job["current_source"],
            "completed_sources": list(job["completed_sources"]),
            "failed_sources": list(job["failed_sources"]),
            "completed_count": len(job["completed_sources"]),
            "failed_count": len(job["failed_sources"]),
            "total_items": int(job["total_items"]),
            "running_sources": list(job.get("running_sources") or []),
            "recent_activity": [
                self._serialize_activity_item(item)
                for item in (job.get("recent_activity") or [])
            ],
            "summary_report": self._build_summary_report(job),
            "progress": self._job_progress(job),
            "created_at": job["created_at"],
            "started_at": job["started_at"],
            "finished_at": job["finished_at"],
            "result_file_name": (
                job["result_file"].name
                if isinstance(job.get("result_file"), Path)
                else None
            ),
            "error_message": job.get("error_message"),
        }

    def _job_to_legacy_status(self, job: dict[str, Any]) -> dict[str, Any]:
        payload = self._serialize_job(job)
        return {
            "is_running": payload["status"] in {"queued", "running", "cancelling"},
            "current_source": payload["current_source"],
            "completed_sources": payload["completed_sources"],
            "failed_sources": payload["failed_sources"],
            "requested_source_count": payload["accepted_source_count"],
            "completed_count": payload["completed_count"],
            "failed_count": payload["failed_count"],
            "total_items": payload["total_items"],
            "running_sources": payload["running_sources"],
            "recent_activity": payload["recent_activity"],
            "summary_report": payload["summary_report"],
            "progress": payload["progress"],
            "started_at": payload["started_at"],
            "finished_at": payload["finished_at"],
            "result_file_name": payload["result_file_name"],
        }

    def _append_activity(
        self,
        job: dict[str, Any],
        *,
        source_id: str,
        phase: str,
        status: str,
        message: str,
        items_total: int = 0,
        db_upserted: int = 0,
        db_new: int = 0,
        db_deduped_in_batch: int = 0,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc),
            "source_id": source_id,
            "phase": phase,
            "status": status,
            "message": message,
            "items_total": int(items_total),
            "db_upserted": int(db_upserted),
            "db_new": int(db_new),
            "db_deduped_in_batch": int(db_deduped_in_batch),
        }
        job["recent_activity"].append(entry)
        if len(job["recent_activity"]) > MAX_ACTIVITY_ENTRIES:
            job["recent_activity"] = job["recent_activity"][-MAX_ACTIVITY_ENTRIES:]

    def _serialize_activity_item(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "timestamp": item.get("timestamp"),
            "source_id": str(item.get("source_id") or ""),
            "phase": str(item.get("phase") or "update"),
            "status": str(item.get("status") or "unknown"),
            "message": str(item.get("message") or ""),
            "items_total": int(item.get("items_total") or 0),
            "db_upserted": int(item.get("db_upserted") or 0),
            "db_new": int(item.get("db_new") or 0),
            "db_deduped_in_batch": int(item.get("db_deduped_in_batch") or 0),
        }

    def _build_summary_report(self, job: dict[str, Any]) -> dict[str, Any]:
        started_at = job.get("started_at")
        finished_at = job.get("finished_at")
        duration_seconds = 0.0
        if isinstance(started_at, datetime) and isinstance(finished_at, datetime):
            duration_seconds = max((finished_at - started_at).total_seconds(), 0.0)
        return {
            "requested_source_count": int(job.get("requested_source_count_effective") or 0),
            "completed_count": len(job.get("completed_sources") or []),
            "failed_count": len(job.get("failed_sources") or []),
            "total_items": int(job.get("total_items") or 0),
            "db_upserted_total": int(job.get("db_upserted_total") or 0),
            "db_new_total": int(job.get("db_new_total") or 0),
            "db_deduped_in_batch_total": int(job.get("db_deduped_in_batch_total") or 0),
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": round(duration_seconds, 2),
            "status": str(job.get("status") or "unknown"),
        }


_control_service: CrawlerControlService | None = None


def get_control_service() -> CrawlerControlService:
    """Get or create the crawler control service singleton."""
    global _control_service
    if _control_service is None:
        _control_service = CrawlerControlService()
    return _control_service


def _load_grouped_crawl_limits() -> dict[str, int]:
    """Load grouped crawl concurrency limits from yaml with safe defaults."""
    defaults = {
        "static": 20,
        "rss": 20,
        "dynamic": 8,
        "snapshot": 10,
        "university_leadership": 6,
    }
    config_path = BASE_DIR / "app" / "config" / "crawl_concurrency.yaml"
    if not config_path.exists():
        return defaults

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read crawl concurrency config, using defaults: %s", exc)
        return defaults

    grouped = loaded.get("grouped") or (loaded.get("strategies") or {}).get("grouped")
    if not isinstance(grouped, dict):
        return defaults

    resolved = dict(defaults)
    for key, value in grouped.items():
        try:
            resolved[str(key)] = max(1, int(value))
        except (TypeError, ValueError):
            continue
    return resolved
