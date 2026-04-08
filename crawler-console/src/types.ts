export interface CrawlHealth {
  total_sources: number;
  enabled_sources: number;
  healthy: number;
  warning: number;
  failing: number;
  last_24h_crawls: number;
  last_24h_new_articles: number;
}

export type JobTransport = "jobs" | "manual-jobs" | "unknown";

export type JobLifecycleStatus =
  | "idle"
  | "queued"
  | "pending"
  | "running"
  | "started"
  | "cancelling"
  | "cancelled"
  | "stopped"
  | "completed"
  | "failed"
  | (string & {});

export interface JobStatus {
  job_id: string | null;
  status: JobLifecycleStatus;
  current_source: string | null;
  running_sources: ManualJobRunningSource[];
  recent_activity: ManualJobActivity[];
  summary_report: ManualJobSummaryReport | null;
  completed_sources: string[];
  failed_sources: string[];
  requested_source_count: number;
  completed_count: number;
  failed_count: number;
  total_items: number;
  progress: number;
  started_at: string | null;
  finished_at: string | null;
  result_file_name: string | null;
  download_url: string | null;
}

export interface ManualJobRunningSource {
  source_id: string;
  source_name?: string | null;
  status?: JobLifecycleStatus | null;
  started_at?: string | null;
}

export interface ManualJobActivity {
  id?: string | null;
  timestamp?: string | null;
  status: string;
  source_id?: string | null;
  source_name?: string | null;
  items_total?: number | null;
  items_new?: number | null;
  inserted_count?: number | null;
  deduped_in_batch?: number | null;
  duration_seconds?: number | null;
  message?: string | null;
}

export interface ManualJobSummaryReport {
  total_sources?: number | null;
  success_count?: number | null;
  failed_count?: number | null;
  total_items?: number | null;
  inserted_count?: number | null;
  deduped_in_batch?: number | null;
  duration_seconds?: number | null;
  started_at?: string | null;
  finished_at?: string | null;
  result_file_name?: string | null;
}

export interface ManualJobStatus extends JobStatus {
  transport: JobTransport;
  is_running: boolean;
}

export interface TodayStats {
  date: string;
  timezone: string;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  no_new_content_runs: number;
  unique_sources: number;
  total_items: number;
  new_items: number;
  average_duration_seconds: number;
  last_run_at: string | null;
}

export interface DimensionSummary {
  dimension: string;
  dimension_name: string | null;
  total_sources: number;
  enabled_sources: number;
  healthy_sources: number;
  warning_sources: number;
  failing_sources: number;
  today_runs: number;
  today_new_items: number;
  last_run_at: string | null;
}

export interface RecentRun {
  source_id: string;
  source_name: string | null;
  dimension: string | null;
  dimension_name: string | null;
  status: string;
  items_total: number;
  items_new: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
}

export interface ConsoleOverview {
  generated_at: string;
  scheduler_status: "running" | "not_started";
  health: CrawlHealth;
  today: TodayStats;
  manual_job: ManualJobStatus;
  dimension_stats: DimensionSummary[];
  recent_runs: RecentRun[];
}

export interface TrendPoint {
  date: string;
  crawls: number;
  success: number;
  failed: number;
  no_new_content: number;
  new_items: number;
  total_items: number;
}

export interface ServerMetrics {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  load_average_1m: number;
  cpu_count: number;
  uptime_seconds: number;
  sampled_at: string;
}

export interface SourceFacetItem {
  key: string;
  label: string | null;
  count: number;
}

export interface SourceDimensionFacetItem extends SourceFacetItem {
  enabled_count: number;
}

export interface SourceFacets {
  dimensions: SourceDimensionFacetItem[];
  groups: SourceFacetItem[];
  tags: SourceFacetItem[];
  crawl_methods: SourceFacetItem[];
  source_types: SourceFacetItem[];
  source_platforms: SourceFacetItem[];
  schedules: SourceFacetItem[];
  health_statuses: SourceFacetItem[];
  taxonomy_domains: SourceFacetItem[];
  taxonomy_tracks: SourceFacetItem[];
  taxonomy_scopes: SourceFacetItem[];
}

export interface SourceItem {
  id: string;
  name: string;
  url: string;
  dimension: string;
  dimension_name: string | null;
  crawl_method: string;
  schedule: string;
  crawl_interval_minutes: number | null;
  is_enabled: boolean;
  priority: number;
  last_crawl_at: string | null;
  last_success_at: string | null;
  consecutive_failures: number;
  source_file: string | null;
  group: string | null;
  tags: string[];
  crawler_class: string | null;
  source_type: string | null;
  source_platform: string | null;
  institution_name: string | null;
  institution_tier: string | null;
  dimension_description: string | null;
  taxonomy_domain: string | null;
  taxonomy_domain_name: string | null;
  taxonomy_track: string | null;
  taxonomy_track_name: string | null;
  taxonomy_scope: string | null;
  taxonomy_scope_name: string | null;
  health_status: "healthy" | "warning" | "failing" | "unknown";
  is_supported: boolean;
  is_enabled_overridden: boolean;
}

export interface SourceCatalogResponse {
  generated_at: string;
  total_sources: number;
  filtered_sources: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: SourceItem[];
  facets: SourceFacets | null;
  applied_filters: Record<string, unknown>;
}

export interface CrawlLog {
  source_id: string;
  status: string;
  items_total: number;
  items_new: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
}

export interface SourceLogsResponse {
  source_id: string;
  logs: CrawlLog[];
}

export interface ManualJobPayload {
  source_ids: string[];
  keyword_filter: string[] | null;
  keyword_blacklist: string[] | null;
  export_format: "json" | "csv" | "database";
}
