<script setup lang="ts">
import { computed } from "vue";

import type { ConsoleOverview, ManualJobActivity, TrendPoint } from "../types";
import StatusSparkline from "./StatusSparkline.vue";
import { formatDateTime, formatNumber, healthLabel } from "../utils/consoleFormat";

const props = defineProps<{
  overview: ConsoleOverview | null;
  trend: TrendPoint[];
  activeTab: "manual" | "trend" | "dimensions" | "runs";
  manualProgressPercent: number;
}>();

const emit = defineEmits<{
  (event: "update:activeTab", value: "manual" | "trend" | "dimensions" | "runs"): void;
}>();

const tabs = [
  { id: "manual", label: "运行中" },
  { id: "trend", label: "7天趋势" },
  { id: "dimensions", label: "维度" },
  { id: "runs", label: "最近记录" },
] as const;

function tabId(tab: (typeof tabs)[number]["id"]) {
  return `intel-tab-${tab}`;
}

function panelId(tab: (typeof tabs)[number]["id"]) {
  return `intel-panel-${tab}`;
}

const manualJob = computed(() => props.overview?.manual_job ?? null);

const runningSources = computed(() => {
  const job = manualJob.value;
  if (!job) {
    return [];
  }
  if (job.running_sources?.length) {
    return job.running_sources;
  }
  if (job.is_running && job.current_source) {
    return [{ source_id: job.current_source, source_name: null, status: "running" as const }];
  }
  return [];
});

const recentActivity = computed(() => manualJob.value?.recent_activity ?? []);
const summaryReport = computed(() => manualJob.value?.summary_report ?? null);
const hasSummaryReport = computed(() => !manualJob.value?.is_running && Boolean(summaryReport.value));

const reportMetrics = computed(() => {
  const report = summaryReport.value;
  const job = manualJob.value;
  if (!report || !job) {
    return [];
  }

  return [
    { label: "总信源", value: formatMetric(report.total_sources ?? job.requested_source_count) },
    {
      label: "成功 / 失败",
      value: `${formatMetric(report.success_count ?? job.completed_count)} / ${formatMetric(report.failed_count ?? job.failed_count)}`,
    },
    { label: "总数据条数", value: formatMetric(report.total_items ?? job.total_items) },
    { label: "入库条数", value: formatMetric(report.inserted_count) },
    { label: "批内去重", value: formatMetric(report.deduped_in_batch) },
    { label: "总耗时", value: formatDuration(report.duration_seconds) },
  ];
});

function formatMetric(value: number | null | undefined) {
  return value === null || value === undefined ? "--" : formatNumber(value);
}

function formatDuration(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "未记录";
  }

  const totalSeconds = Math.max(0, Math.round(value));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}小时 ${minutes}分`;
  }
  if (minutes > 0) {
    return `${minutes}分 ${seconds}秒`;
  }
  return `${seconds}秒`;
}

function manualStatusLabel(status: string | null | undefined) {
  const mapping: Record<string, string> = {
    running: "运行中",
    queued: "排队中",
    pending: "准备中",
    started: "启动中",
    cancelling: "停止中",
    cancelled: "已取消",
    stopped: "已停止",
    completed: "已完成",
    failed: "失败",
    success: "成功",
    no_new_content: "无新增",
    idle: "空闲",
    info: "信息",
  };

  return mapping[status || ""] || healthLabel(status || "unknown");
}

function activityKey(activity: ManualJobActivity, index: number) {
  return activity.id || `${activity.timestamp || "no-time"}-${activity.source_id || "system"}-${index}`;
}

function activitySubject(activity: ManualJobActivity) {
  return activity.source_name || activity.source_id || "系统";
}

function activityResult(activity: ManualJobActivity) {
  const fragments: string[] = [];

  if (activity.items_new !== null && activity.items_new !== undefined) {
    fragments.push(`新增 ${formatNumber(activity.items_new)}`);
  }
  if (activity.items_total !== null && activity.items_total !== undefined) {
    fragments.push(`总计 ${formatNumber(activity.items_total)}`);
  }
  if (activity.inserted_count !== null && activity.inserted_count !== undefined) {
    fragments.push(`入库 ${formatNumber(activity.inserted_count)}`);
  }
  if (activity.deduped_in_batch !== null && activity.deduped_in_batch !== undefined) {
    fragments.push(`去重 ${formatNumber(activity.deduped_in_batch)}`);
  }
  if (!fragments.length && activity.duration_seconds !== null && activity.duration_seconds !== undefined) {
    fragments.push(`耗时 ${formatDuration(activity.duration_seconds)}`);
  }

  return fragments.join(" · ") || activity.message || "等待结果回传";
}
</script>

<template>
  <section class="intel-dock panel">
    <div class="panel-header dock-header">
      <div>
        <p class="eyebrow">Intel Dock</p>
        <h2>运行情报坞</h2>
        <p class="panel-note">
          {{
            manualJob?.is_running
              ? `运行中 ${manualProgressPercent}% · ${runningSources.length} 路并行`
              : hasSummaryReport
                ? "任务已完成，已生成本批次报告"
                : "当前空闲，默认查看最近记录"
          }}
        </p>
      </div>
      <div class="dock-tabs" role="tablist" aria-label="运行情报">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :id="tabId(tab.id)"
          :class="['dock-tab', { 'is-active': activeTab === tab.id }]"
          role="tab"
          :aria-selected="activeTab === tab.id"
          :aria-controls="panelId(tab.id)"
          :tabindex="activeTab === tab.id ? 0 : -1"
          type="button"
          @click="emit('update:activeTab', tab.id)"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <div
      v-if="activeTab === 'manual'"
      :id="panelId('manual')"
      class="dock-panel"
      role="tabpanel"
      :aria-labelledby="tabId('manual')"
      tabindex="0"
    >
      <div class="dock-manual-head dock-manual-head-terminal">
        <div>
          <strong>
            {{ manualJob?.is_running ? "并行任务执行中" : hasSummaryReport ? "任务报告" : "当前空闲" }}
          </strong>
          <p class="panel-note">
            {{
              manualJob?.is_running
                ? `已完成 ${manualJob?.completed_count || 0} / ${manualJob?.requested_source_count || 0}`
                : hasSummaryReport
                  ? `完成于 ${formatDateTime(summaryReport?.finished_at || manualJob?.finished_at || null)}`
                  : "暂无运行中的手动任务"
            }}
          </p>
        </div>
        <div class="dock-terminal-progress-meta">
          <span class="status-pill" :data-status="manualJob?.is_running ? 'running' : manualJob?.status || 'idle'">
            {{ manualStatusLabel(manualJob?.is_running ? "running" : manualJob?.status) }}
          </span>
          <span>{{ manualProgressPercent }}%</span>
        </div>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: `${manualProgressPercent}%` }" />
      </div>
      <div v-if="manualJob?.is_running" class="dock-terminal-shell">
        <section class="dock-terminal-panel">
          <div class="dock-terminal-header">
            <strong>并行执行列表</strong>
            <span>{{ runningSources.length }} 路</span>
          </div>
          <div class="dock-terminal-list">
            <div v-for="source in runningSources" :key="source.source_id" class="dock-terminal-line">
              <span class="dock-terminal-prefix">run</span>
              <span class="status-pill" :data-status="source.status || 'running'">
                {{ manualStatusLabel(source.status || "running") }}
              </span>
              <strong>{{ source.source_name || source.source_id }}</strong>
              <span class="dock-terminal-line-meta">{{ source.source_id }}</span>
            </div>
            <div v-if="!runningSources.length" class="dock-terminal-empty">
              已启动任务，等待并行信源列表回传
            </div>
          </div>
        </section>

        <section class="dock-terminal-panel">
          <div class="dock-terminal-header">
            <strong>Recent Activity</strong>
            <span>{{ recentActivity.length }} 条</span>
          </div>
          <div class="dock-terminal-feed">
            <article
              v-for="(activity, index) in recentActivity"
              :key="activityKey(activity, index)"
              class="dock-terminal-entry"
            >
              <span class="dock-terminal-time">{{ formatDateTime(activity.timestamp || null) }}</span>
              <span class="status-pill" :data-status="activity.status">{{ manualStatusLabel(activity.status) }}</span>
              <strong class="dock-terminal-source">{{ activitySubject(activity) }}</strong>
              <span class="dock-terminal-result">{{ activityResult(activity) }}</span>
            </article>
            <div v-if="!recentActivity.length" class="dock-terminal-empty">
              任务已启动，等待活动日志回传
            </div>
          </div>
        </section>
      </div>

      <div v-else-if="hasSummaryReport" class="dock-report-stack">
        <section class="dock-report-card">
          <div class="dock-terminal-header">
            <strong>任务报告</strong>
            <span>{{ summaryReport?.result_file_name || manualJob?.result_file_name || "无导出文件" }}</span>
          </div>
          <div class="dock-report-grid">
            <article v-for="metric in reportMetrics" :key="metric.label">
              <span>{{ metric.label }}</span>
              <strong>{{ metric.value }}</strong>
            </article>
          </div>
        </section>

        <section class="dock-terminal-panel">
          <div class="dock-terminal-header">
            <strong>Recent Activity</strong>
            <span>{{ recentActivity.length }} 条</span>
          </div>
          <div class="dock-terminal-feed">
            <article
              v-for="(activity, index) in recentActivity"
              :key="activityKey(activity, index)"
              class="dock-terminal-entry"
            >
              <span class="dock-terminal-time">{{ formatDateTime(activity.timestamp || null) }}</span>
              <span class="status-pill" :data-status="activity.status">{{ manualStatusLabel(activity.status) }}</span>
              <strong class="dock-terminal-source">{{ activitySubject(activity) }}</strong>
              <span class="dock-terminal-result">{{ activityResult(activity) }}</span>
            </article>
            <div v-if="!recentActivity.length" class="dock-terminal-empty">
              本次任务未返回活动明细
            </div>
          </div>
        </section>
      </div>

      <div v-else class="dock-terminal-panel dock-terminal-idle">
        <div class="dock-terminal-header">
          <strong>任务状态</strong>
          <span>{{ manualJob?.result_file_name || "无历史导出" }}</span>
        </div>
        <div class="dock-terminal-empty">
          暂无运行中的手动任务，也没有可展示的完成报告
        </div>
      </div>
    </div>

    <div
      v-else-if="activeTab === 'trend'"
      :id="panelId('trend')"
      class="dock-panel trend-panel"
      role="tabpanel"
      :aria-labelledby="tabId('trend')"
      tabindex="0"
    >
      <StatusSparkline :values="trend.map((item) => item.crawls)" />
      <div class="dock-list">
        <div v-for="point in trend" :key="point.date" class="dock-row">
          <span>{{ point.date }}</span>
          <strong>{{ point.crawls }} 次</strong>
          <span>{{ point.new_items }} 新增</span>
        </div>
        <div v-if="!trend.length" class="section-empty">暂无趋势数据</div>
      </div>
    </div>

    <div
      v-else-if="activeTab === 'dimensions'"
      :id="panelId('dimensions')"
      class="dock-panel"
      role="tabpanel"
      :aria-labelledby="tabId('dimensions')"
      tabindex="0"
    >
      <div class="dock-list">
        <div v-for="item in overview?.dimension_stats || []" :key="item.dimension" class="dock-row">
          <div>
            <strong>{{ item.dimension_name || item.dimension }}</strong>
            <p>{{ item.enabled_sources }}/{{ item.total_sources }} 启用</p>
          </div>
          <div class="dock-row-meta">
            <span>{{ item.today_runs }} 次</span>
            <span>{{ item.today_new_items }} 新增</span>
          </div>
        </div>
        <div v-if="!(overview?.dimension_stats || []).length" class="section-empty">暂无维度统计</div>
      </div>
    </div>

    <div
      v-else
      :id="panelId('runs')"
      class="dock-panel"
      role="tabpanel"
      :aria-labelledby="tabId('runs')"
      tabindex="0"
    >
      <div class="dock-list">
        <div v-for="run in overview?.recent_runs || []" :key="`${run.source_id}-${run.started_at}`" class="dock-row">
          <div>
            <strong>{{ run.source_name || run.source_id }}</strong>
            <p>{{ formatDateTime(run.started_at) }}</p>
          </div>
          <div class="dock-row-meta">
            <span class="status-pill" :data-status="run.status">{{ healthLabel(run.status) }}</span>
            <span>{{ run.items_new }} / {{ run.items_total }}</span>
          </div>
        </div>
        <div v-if="!(overview?.recent_runs || []).length" class="section-empty">暂无运行记录</div>
      </div>
    </div>
  </section>
</template>
