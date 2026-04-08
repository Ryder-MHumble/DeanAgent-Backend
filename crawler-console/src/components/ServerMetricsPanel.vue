<script setup lang="ts">
import { computed } from "vue";

import type { ServerMetrics } from "../types";
import { formatDateTime, formatNumber } from "../utils/consoleFormat";

const props = defineProps<{
  metrics: ServerMetrics | null;
  errorMessage?: string;
}>();

const utilizationRows = computed(() => {
  if (!props.metrics) {
    return [];
  }

  return [
    { key: "cpu", label: "CPU", percent: props.metrics.cpu_percent },
    { key: "memory", label: "内存", percent: props.metrics.memory_percent },
    { key: "disk", label: "磁盘", percent: props.metrics.disk_percent },
  ];
});

function pressureLevel(percent: number) {
  if (percent >= 85) {
    return "高";
  }
  if (percent >= 60) {
    return "中";
  }
  return "低";
}

function formatUptime(seconds: number) {
  const totalMinutes = Math.max(0, Math.floor(seconds / 60));
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;

  if (days > 0) {
    return `${days}天 ${hours}小时`;
  }
  if (hours > 0) {
    return `${hours}小时 ${minutes}分钟`;
  }
  return `${minutes}分钟`;
}

const hostSummary = computed(() => {
  if (!props.metrics) {
    return null;
  }

  const pressure = (props.metrics.cpu_percent + props.metrics.memory_percent + props.metrics.disk_percent) / 3;
  const loadPerCore =
    props.metrics.cpu_count > 0 ? props.metrics.load_average_1m / props.metrics.cpu_count : props.metrics.load_average_1m;

  return {
    pressure,
    pressureLabel: pressureLevel(pressure),
    loadPerCore,
    uptimeText: formatUptime(props.metrics.uptime_seconds),
  };
});

const metricRows = computed(() => {
  if (!props.metrics) {
    return [];
  }
  return [
    { label: "1m 负载", value: formatNumber(props.metrics.load_average_1m), hint: "越接近 CPU 核数越繁忙" },
    { label: "单核负载", value: formatNumber(hostSummary.value?.loadPerCore || 0), hint: "1m负载 / CPU核数" },
    { label: "CPU 核数", value: formatNumber(props.metrics.cpu_count) },
    { label: "运行时长", value: hostSummary.value?.uptimeText || "-" },
    { label: "采样周期", value: "10 秒", hint: "与控制台刷新保持一致" },
    { label: "采样时间", value: formatDateTime(props.metrics.sampled_at), hint: "用于判断数据时效" },
  ];
});
</script>

<template>
  <aside class="server-panel">
    <header class="server-panel-head">
      <p class="eyebrow">Server</p>
      <h3>主机指标</h3>
      <p class="server-panel-time">
        {{ metrics ? formatDateTime(metrics.sampled_at) : "等待采样" }}
      </p>
    </header>

    <p v-if="errorMessage" class="server-panel-error">{{ errorMessage }}</p>

    <template v-else-if="metricRows.length">
      <section class="server-summary-cards">
        <article class="server-summary-main">
          <span>主机压力指数</span>
          <strong>{{ formatNumber(hostSummary?.pressure || 0) }}%</strong>
          <em :data-level="hostSummary?.pressureLabel || '低'">{{ hostSummary?.pressureLabel || "低" }}负载</em>
        </article>
        <article>
          <span>单核负载</span>
          <strong>{{ formatNumber(hostSummary?.loadPerCore || 0) }}</strong>
        </article>
        <article>
          <span>稳定运行</span>
          <strong>{{ hostSummary?.uptimeText || "-" }}</strong>
        </article>
      </section>

      <section class="server-utilization">
        <article v-for="row in utilizationRows" :key="row.key">
          <div class="server-util-head">
            <span>{{ row.label }}</span>
            <strong>{{ formatNumber(row.percent) }}%</strong>
          </div>
          <div class="server-util-track">
            <div class="server-util-fill" :data-level="pressureLevel(row.percent)" :style="{ width: `${Math.min(100, Math.max(0, row.percent))}%` }" />
          </div>
        </article>
      </section>

      <div class="server-panel-grid">
      <article v-for="row in metricRows" :key="row.label">
        <span>{{ row.label }}</span>
        <strong>{{ row.value }}</strong>
        <small v-if="row.hint">{{ row.hint }}</small>
      </article>
      </div>
    </template>

    <p v-else class="server-panel-empty">暂无服务器指标数据</p>
  </aside>
</template>

<style scoped>
.server-panel {
  display: grid;
  gap: 14px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  background:
    linear-gradient(180deg, rgba(11, 17, 24, 0.92), rgba(9, 13, 20, 0.96)),
    radial-gradient(circle at top right, rgba(96, 227, 196, 0.12), transparent 38%);
}

.server-panel-head {
  display: grid;
  gap: 6px;
}

.server-panel-head h3 {
  margin: 0;
}

.server-panel-time,
.server-panel-empty,
.server-panel-error,
.server-panel-grid span,
.server-util-head span,
.server-summary-cards span,
.server-summary-cards em,
.server-panel-grid small {
  color: var(--muted);
}

.server-summary-cards {
  display: grid;
  grid-template-columns: 1.3fr 1fr 1fr;
  gap: 10px;
}

.server-summary-cards article {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(255, 255, 255, 0.03);
}

.server-summary-main {
  background: linear-gradient(180deg, rgba(105, 212, 255, 0.12), rgba(105, 212, 255, 0.04));
  border-color: rgba(105, 212, 255, 0.2);
}

.server-summary-cards strong {
  font-size: 22px;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.server-summary-cards em {
  font-style: normal;
  font-size: 12px;
}

.server-summary-cards em[data-level="高"] {
  color: #ff7f7f;
}

.server-summary-cards em[data-level="中"] {
  color: #ffbe63;
}

.server-summary-cards em[data-level="低"] {
  color: #3dd8a1;
}

.server-utilization {
  display: grid;
  gap: 10px;
}

.server-utilization article {
  display: grid;
  gap: 8px;
}

.server-util-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
}

.server-util-head strong {
  font-variant-numeric: tabular-nums;
}

.server-util-track {
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.08);
}

.server-util-fill {
  height: 100%;
  border-radius: inherit;
  background: rgba(61, 216, 161, 0.7);
}

.server-util-fill[data-level="中"] {
  background: rgba(255, 190, 99, 0.8);
}

.server-util-fill[data-level="高"] {
  background: rgba(255, 127, 127, 0.85);
}

.server-panel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.server-panel-grid article {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.server-panel-grid strong {
  font-variant-numeric: tabular-nums;
}

.server-panel-grid small {
  grid-column: 1 / -1;
  font-size: 11px;
}

.server-panel-error {
  color: #f7b538;
}

@media (max-width: 980px) {
  .server-summary-cards {
    grid-template-columns: 1fr;
  }

  .server-panel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
