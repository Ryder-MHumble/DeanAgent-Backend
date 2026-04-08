import type {
  ConsoleOverview,
  JobTransport,
  ManualJobPayload,
  ManualJobStatus,
  ServerMetrics,
  SourceCatalogResponse,
  SourceItem,
  SourceLogsResponse,
  TrendPoint,
} from "../types";

const API_BASE = (import.meta.env.VITE_CONSOLE_API_BASE || "/console-api").replace(/\/$/, "");

type JsonRecord = Record<string, unknown>;
type RawConsoleOverview = Omit<ConsoleOverview, "manual_job"> & { manual_job?: unknown };

const FALLBACK_STATUSES = new Set([404, 405, 501]);
const RUNNING_JOB_STATUSES = new Set(["queued", "pending", "running", "started", "cancelling"]);
const TERMINAL_JOB_STATUSES = new Set(["completed", "failed", "cancelled", "stopped"]);

let lastKnownJobId: string | null = null;
let lastKnownJobTransport: JobTransport = "unknown";

class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(status: number, message: string, payload?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function buildQuery(params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") {
      return;
    }
    search.set(key, String(value));
  });
  const serialized = search.toString();
  return serialized ? `?${serialized}` : "";
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function asBoolean(value: unknown): boolean | null {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    if (value === "true") {
      return true;
    }
    if (value === "false") {
      return false;
    }
  }
  return null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => asString(item))
    .filter((item): item is string => item !== null);
}

function pickString(record: JsonRecord, keys: string[]): string | null {
  for (const key of keys) {
    const value = asString(record[key]);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

function pickNumber(record: JsonRecord, keys: string[]): number | null {
  for (const key of keys) {
    const value = asNumber(record[key]);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

function pickBoolean(record: JsonRecord, keys: string[]): boolean | null {
  for (const key of keys) {
    const value = asBoolean(record[key]);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

function clampProgress(value: number | null): number {
  if (value === null || Number.isNaN(value)) {
    return 0;
  }
  const normalized = value > 1 ? value / 100 : value;
  return Math.min(Math.max(normalized, 0), 1);
}

function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

function shouldFallbackToLegacy(error: unknown): boolean {
  return isApiError(error) && FALLBACK_STATUSES.has(error.status);
}

function buildLegacyDownloadUrl() {
  return `${API_BASE}/manual-jobs/download`;
}

function buildJobDownloadUrl(jobId: string) {
  return `${API_BASE}/jobs/${encodeURIComponent(jobId)}/result`;
}

function syncJobContext(status: ManualJobStatus) {
  if (status.transport !== "unknown") {
    lastKnownJobTransport = status.transport;
  }
  if (status.job_id) {
    lastKnownJobId = status.job_id;
  }
}

function normalizeJobStatus(
  payload: unknown,
  options: {
    fallbackJobId?: string | null;
    transport?: JobTransport;
    fallbackDownloadUrl?: string | null;
  } = {},
): ManualJobStatus {
  const record = isRecord(payload) ? payload : {};
  const progressRecord = isRecord(record.progress) ? record.progress : null;
  const resultRecord = isRecord(record.result) ? record.result : null;
  const countsRecord = isRecord(record.counts) ? record.counts : null;

  const completedSources = asStringArray(record.completed_sources);
  const failedSources = asStringArray(record.failed_sources);
  const jobId = pickString(record, ["job_id", "id"]) ?? options.fallbackJobId ?? null;
  const status =
    pickString(record, ["status", "state"]) ??
    (pickBoolean(record, ["is_running", "running"]) ? "running" : "idle");

  const requestedSourceCount =
    pickNumber(record, ["requested_source_count", "requested_count", "accepted_source_count"]) ??
    (countsRecord ? pickNumber(countsRecord, ["requested", "total"]) : null) ??
    completedSources.length + failedSources.length;

  const completedCount =
    pickNumber(record, ["completed_count", "success_count"]) ??
    (countsRecord ? pickNumber(countsRecord, ["completed", "succeeded"]) : null) ??
    completedSources.length;

  const failedCount =
    pickNumber(record, ["failed_count", "error_count"]) ??
    (countsRecord ? pickNumber(countsRecord, ["failed", "errors"]) : null) ??
    failedSources.length;

  const totalItems =
    pickNumber(record, ["total_items", "items_total"]) ??
    (countsRecord ? pickNumber(countsRecord, ["items_total", "total_items"]) : null) ??
    0;

  const explicitProgress =
    pickNumber(record, ["progress", "progress_ratio", "completion_ratio"]) ??
    (progressRecord ? pickNumber(progressRecord, ["ratio", "percent", "value"]) : null);
  const derivedProgress = requestedSourceCount > 0 ? (completedCount + failedCount) / requestedSourceCount : 0;

  const isRunning =
    pickBoolean(record, ["is_running", "running"]) ??
    RUNNING_JOB_STATUSES.has(status);

  const resultFileName =
    pickString(record, ["result_file_name", "file_name"]) ??
    (resultRecord ? pickString(resultRecord, ["file_name", "name"]) : null);

  const downloadUrl =
    pickString(record, ["download_url", "result_url"]) ??
    (resultRecord ? pickString(resultRecord, ["download_url", "url"]) : null) ??
    (jobId && options.transport === "jobs" ? buildJobDownloadUrl(jobId) : options.fallbackDownloadUrl ?? null);

  return {
    job_id: jobId,
    status,
    current_source: pickString(record, ["current_source", "active_source", "source_id"]),
    completed_sources: completedSources,
    failed_sources: failedSources,
    requested_source_count: Math.max(requestedSourceCount, 0),
    completed_count: Math.max(completedCount, completedSources.length),
    failed_count: Math.max(failedCount, failedSources.length),
    total_items: Math.max(totalItems, 0),
    progress: clampProgress(explicitProgress ?? derivedProgress),
    started_at: pickString(record, ["started_at", "created_at"]),
    finished_at: pickString(record, ["finished_at", "updated_at"]),
    result_file_name: resultFileName,
    download_url: downloadUrl,
    transport: options.transport ?? (jobId ? "jobs" : "manual-jobs"),
    is_running: isRunning,
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  const contentType = response.headers.get("content-type") || "";
  let payload: unknown = null;

  if (response.status !== 204) {
    if (contentType.includes("application/json")) {
      payload = await response.json();
    } else {
      const text = await response.text();
      payload = text || null;
    }
  }

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    if (isRecord(payload)) {
      message = asString(payload.detail) || asString(payload.message) || message;
    } else if (typeof payload === "string" && payload.trim()) {
      message = payload;
    }
    throw new ApiError(response.status, message, payload);
  }

  return payload as T;
}

async function getLegacyManualJobStatus() {
  const payload = await request<unknown>("/manual-jobs/status");
  const status = normalizeJobStatus(payload, {
    transport: "manual-jobs",
    fallbackDownloadUrl: buildLegacyDownloadUrl(),
  });
  syncJobContext(status);
  return status;
}

async function getJobStatus(jobId?: string | null) {
  const candidateJobId = jobId ?? lastKnownJobId;
  if (candidateJobId) {
    try {
      const payload = await request<unknown>(`/jobs/${encodeURIComponent(candidateJobId)}`);
      const status = normalizeJobStatus(payload, {
        fallbackJobId: candidateJobId,
        transport: "jobs",
        fallbackDownloadUrl: buildJobDownloadUrl(candidateJobId),
      });
      syncJobContext(status);
      return status;
    } catch (error) {
      if (!shouldFallbackToLegacy(error)) {
        throw error;
      }
    }
  }

  return getLegacyManualJobStatus();
}

async function createJob(payload: ManualJobPayload) {
  try {
    const response = await request<unknown>("/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const created = normalizeJobStatus(response, { transport: "jobs" });
    syncJobContext(created);
    if (created.job_id) {
      return await getJobStatus(created.job_id);
    }
    return created;
  } catch (error) {
    if (!shouldFallbackToLegacy(error)) {
      throw error;
    }
  }

  await request<unknown>("/manual-jobs/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return getLegacyManualJobStatus();
}

async function cancelJob(jobId?: string | null) {
  const candidateJobId = jobId ?? lastKnownJobId;
  if (candidateJobId) {
    try {
      const response = await request<unknown>(`/jobs/${encodeURIComponent(candidateJobId)}/cancel`, {
        method: "POST",
      });
      const cancelled = normalizeJobStatus(response, {
        fallbackJobId: candidateJobId,
        transport: "jobs",
        fallbackDownloadUrl: buildJobDownloadUrl(candidateJobId),
      });
      syncJobContext(cancelled);
      if (!TERMINAL_JOB_STATUSES.has(cancelled.status)) {
        return await getJobStatus(candidateJobId);
      }
      return cancelled;
    } catch (error) {
      if (!shouldFallbackToLegacy(error)) {
        throw error;
      }
    }
  }

  await request<unknown>("/manual-jobs/stop", {
    method: "POST",
  });
  return getLegacyManualJobStatus();
}

export const consoleApi = {
  async getOverview(activeJobId?: string | null) {
    const response = await request<RawConsoleOverview>("/overview");
    let manualJob = normalizeJobStatus(response.manual_job, {
      fallbackJobId: activeJobId ?? lastKnownJobId,
      fallbackDownloadUrl: buildLegacyDownloadUrl(),
    });

    if (manualJob.job_id || activeJobId || manualJob.is_running) {
      try {
        manualJob = await getJobStatus(manualJob.job_id ?? activeJobId ?? null);
      } catch {
        // Keep overview available even if dedicated job status probing fails.
      }
    }

    syncJobContext(manualJob);
    return {
      ...response,
      manual_job: manualJob,
    } satisfies ConsoleOverview;
  },
  getDailyTrend(days = 7) {
    return request<TrendPoint[]>(`/daily-trend${buildQuery({ days })}`);
  },
  getServerMetrics() {
    return request<ServerMetrics>("/server-metrics");
  },
  getSources(params: Record<string, string | number | boolean | null | undefined>) {
    return request<SourceCatalogResponse>(`/sources${buildQuery(params)}`);
  },
  getSourceLogs(sourceId: string, limit = 20) {
    return request<SourceLogsResponse>(
      `/sources/${encodeURIComponent(sourceId)}/logs${buildQuery({ limit })}`,
    );
  },
  updateSource(sourceId: string, isEnabled: boolean) {
    return request<SourceItem>(`/sources/${encodeURIComponent(sourceId)}`, {
      method: "PATCH",
      body: JSON.stringify({ is_enabled: isEnabled }),
    });
  },
  triggerSource(sourceId: string) {
    return request<{ status: string; source_id: string }>(
      `/sources/${encodeURIComponent(sourceId)}/trigger`,
      {
        method: "POST",
      },
    );
  },
  startManualJob: createJob,
  stopManualJob: cancelJob,
  getManualJobStatus: getJobStatus,
  getDownloadUrl(jobId?: string | null) {
    const candidateJobId = jobId ?? lastKnownJobId;
    if (candidateJobId && lastKnownJobTransport !== "manual-jobs") {
      return buildJobDownloadUrl(candidateJobId);
    }
    return buildLegacyDownloadUrl();
  },
};
