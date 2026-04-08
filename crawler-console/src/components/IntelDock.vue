<script setup lang="ts">
import type { ConsoleOverview, TrendPoint } from "../types";
import StatusSparkline from "./StatusSparkline.vue";
import { formatDateTime, healthLabel } from "../utils/consoleFormat";

defineProps<{
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
</script>

<template>
  <section class="intel-dock panel">
    <div class="panel-header dock-header">
      <div>
        <p class="eyebrow">Intel Dock</p>
        <h2>运行情报坞</h2>
        <p class="panel-note">
          {{ overview?.manual_job.is_running ? `运行中 ${manualProgressPercent}%` : "当前空闲，默认查看最近记录" }}
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
      <div class="dock-manual-head">
        <strong>{{ overview?.manual_job.is_running ? "任务执行中" : "当前空闲" }}</strong>
        <span>{{ manualProgressPercent }}%</span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: `${manualProgressPercent}%` }" />
      </div>
      <div class="dock-grid">
        <div>
          <span>当前信源</span>
          <strong>{{ overview?.manual_job.current_source || "空闲" }}</strong>
        </div>
        <div>
          <span>已完成</span>
          <strong>
            {{ overview?.manual_job.completed_count || 0 }}/{{ overview?.manual_job.requested_source_count || 0 }}
          </strong>
        </div>
        <div>
          <span>失败</span>
          <strong>{{ overview?.manual_job.failed_count || 0 }}</strong>
        </div>
        <div>
          <span>输出文件</span>
          <strong>{{ overview?.manual_job.result_file_name || "暂无" }}</strong>
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
