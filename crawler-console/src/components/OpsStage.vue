<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { ConsoleOverview, ServerMetrics, TrendPoint } from "../types";
import { formatNumber, formatShortDate } from "../utils/consoleFormat";
import ServerMetricsPanel from "./ServerMetricsPanel.vue";

const props = defineProps<{
  overview: ConsoleOverview | null;
  trend: TrendPoint[];
  serverMetrics: ServerMetrics | null;
  serverError?: string;
}>();

interface ChartPoint {
  x: number;
  y: number;
}

interface ChartPath {
  line: string;
  area: string;
  points: ChartPoint[];
}

function buildPath(
  values: number[],
  width: number,
  height: number,
  topPadding: number,
  bottomPadding: number,
  maxValue: number,
): ChartPath {
  if (!values.length) {
    return { line: "", area: "", points: [] };
  }

  const max = Math.max(maxValue, 1);
  const usableHeight = height - topPadding - bottomPadding;
  const step = values.length > 1 ? width / (values.length - 1) : width;
  const points = values.map((value, index) => ({
    x: index * step,
    y: height - bottomPadding - (value / max) * usableHeight,
  }));

  const line = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");
  const lastPoint = points[points.length - 1];
  const area = lastPoint
    ? `${line} L ${lastPoint.x} ${height - bottomPadding} L 0 ${height - bottomPadding} Z`
    : "";

  return { line, area, points };
}

const chartWidth = 700;
const chartHeight = 240;
const topPadding = 20;
const bottomPadding = 26;
const activeIndex = ref(0);

watch(
  () => props.trend.length,
  (length) => {
    activeIndex.value = length > 0 ? length - 1 : 0;
  },
  { immediate: true },
);

const safeActiveIndex = computed(() =>
  props.trend.length ? Math.min(activeIndex.value, props.trend.length - 1) : 0,
);

const activePoint = computed(() => props.trend[safeActiveIndex.value] || null);

const chartMax = computed(() =>
  Math.max(
    ...props.trend.flatMap((item) => [item.crawls, item.success, item.failed]),
    1,
  ),
);

const crawlsPath = computed(() =>
  buildPath(
    props.trend.map((item) => item.crawls),
    chartWidth,
    chartHeight,
    topPadding,
    bottomPadding,
    chartMax.value,
  ),
);

const successPath = computed(() =>
  buildPath(
    props.trend.map((item) => item.success),
    chartWidth,
    chartHeight,
    topPadding,
    bottomPadding,
    chartMax.value,
  ),
);

const failedPath = computed(() =>
  buildPath(
    props.trend.map((item) => item.failed),
    chartWidth,
    chartHeight,
    topPadding,
    bottomPadding,
    chartMax.value,
  ),
);

const activeMarkers = computed(() => {
  const index = safeActiveIndex.value;
  return {
    crawls: crawlsPath.value.points[index] || null,
    success: successPath.value.points[index] || null,
    failed: failedPath.value.points[index] || null,
  };
});

const chartLabels = computed(() => props.trend.map((item) => formatShortDate(item.date)));

const stageSummary = computed(() => {
  const totals = props.trend.reduce(
    (accumulator, point) => {
      accumulator.crawls += point.crawls;
      accumulator.success += point.success;
      accumulator.failed += point.failed;
      accumulator.noNew += point.no_new_content;
      accumulator.newItems += point.new_items;
      if (point.failed > accumulator.peak.failed) {
        accumulator.peak = { failed: point.failed, date: point.date };
      }
      return accumulator;
    },
    {
      crawls: 0,
      success: 0,
      failed: 0,
      noNew: 0,
      newItems: 0,
      peak: { failed: 0, date: "" },
    },
  );

  const successRate = totals.crawls ? Math.round((totals.success / totals.crawls) * 100) : 0;
  const noNewRatio = totals.crawls ? Math.round((totals.noNew / totals.crawls) * 100) : 0;

  return [
    {
      label: "7 日总运行",
      value: formatNumber(totals.crawls),
      note: `${formatNumber(totals.success)} 次成功 / ${formatNumber(totals.failed)} 次失败`,
    },
    {
      label: "平均成功率",
      value: totals.crawls ? `${successRate}%` : "暂无数据",
      note: `${formatNumber(totals.noNew)} 次无新增，占比 ${noNewRatio}%`,
    },
    {
      label: "失败峰值",
      value: formatNumber(totals.peak.failed),
      note: totals.peak.date ? `${formatShortDate(totals.peak.date)} 触顶` : "近 7 天无失败",
    },
    {
      label: "7 日新增内容",
      value: formatNumber(totals.newItems),
      note: `${formatNumber(props.overview?.today.new_items || 0)} 条来自今日`,
    },
  ];
});

const stageHeaderStats = computed(() => {
  const totalRuns = props.overview?.today.total_runs || 0;
  const successRuns = props.overview?.today.successful_runs || 0;
  const successRate = totalRuns ? Math.round((successRuns / totalRuns) * 100) : 0;
  const sevenDayNewItems = props.trend.reduce((sum, item) => sum + item.new_items, 0);

  return [
    { label: "今日运行", value: formatNumber(totalRuns) },
    { label: "今日成功率", value: totalRuns ? `${successRate}%` : "暂无数据" },
    { label: "7 日新增", value: formatNumber(sevenDayNewItems) },
  ];
});

const focusMetrics = computed(() => {
  if (!activePoint.value) {
    return [];
  }

  const successRate = activePoint.value.crawls
    ? Math.round((activePoint.value.success / activePoint.value.crawls) * 100)
    : 0;

  return [
    { label: "总运行", value: `${formatNumber(activePoint.value.crawls)} 次`, tone: "crawls" },
    { label: "成功", value: `${formatNumber(activePoint.value.success)} 次`, tone: "success" },
    { label: "失败", value: `${formatNumber(activePoint.value.failed)} 次`, tone: "failed" },
    { label: "无新增", value: `${formatNumber(activePoint.value.no_new_content)} 次`, tone: "muted" },
    { label: "新增内容", value: `${formatNumber(activePoint.value.new_items)} 条`, tone: "muted" },
    { label: "成功率", value: `${successRate}%`, tone: "success" },
  ];
});

const tooltipStyle = computed(() => {
  const marker = activeMarkers.value.crawls;
  if (!marker) {
    return {};
  }

  const clampedLeft = Math.max(88, Math.min(chartWidth - 88, marker.x));
  const top = Math.max(18, marker.y - 14);
  return {
    left: `${clampedLeft}px`,
    top: `${top}px`,
  };
});

const tooltipStats = computed(() => {
  if (!activePoint.value) {
    return null;
  }
  const successRate = activePoint.value.crawls
    ? Math.round((activePoint.value.success / activePoint.value.crawls) * 100)
    : 0;

  return {
    date: formatShortDate(activePoint.value.date),
    crawls: activePoint.value.crawls,
    success: activePoint.value.success,
    failed: activePoint.value.failed,
    noNew: activePoint.value.no_new_content,
    newItems: activePoint.value.new_items,
    successRate,
  };
});
</script>

<template>
  <section class="ops-stage panel">
    <div class="ops-stage-main">
      <header class="ops-stage-head">
        <div>
          <p class="eyebrow">Ops Stage</p>
          <h2>运行舞台</h2>
          <p class="ops-stage-subtitle">近 7 天爬虫走势与当前服务器占用收敛在同一块首屏工作面，先判断异常，再决定动作。</p>
        </div>

        <div class="ops-stage-head-meta">
          <div v-for="item in stageHeaderStats" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </header>

      <div class="ops-stage-chart-shell">
        <div class="ops-stage-legend">
          <span><i class="legend-dot legend-crawls"></i>总运行</span>
          <span><i class="legend-dot legend-success"></i>成功</span>
          <span><i class="legend-dot legend-failed"></i>失败</span>
        </div>

        <div v-if="activePoint" class="ops-stage-focus">
          <div class="ops-stage-focus-copy">
            <span class="ops-stage-focus-label">当前焦点</span>
            <strong>{{ formatShortDate(activePoint.date) }}</strong>
            <p>{{ activePoint.no_new_content }} 次无新增，{{ formatNumber(activePoint.new_items) }} 条新增内容。</p>
          </div>
          <div class="ops-stage-focus-grid">
            <span
              v-for="item in focusMetrics"
              :key="item.label"
              :data-tone="item.tone"
              class="ops-stage-focus-chip"
            >
              {{ item.label }} {{ item.value }}
            </span>
          </div>
        </div>

        <div class="ops-stage-plot">
          <svg viewBox="0 0 700 240" preserveAspectRatio="none" class="ops-stage-chart" aria-label="近 7 天爬虫趋势">
            <defs>
              <linearGradient id="ops-area-crawls" x1="0%" x2="0%" y1="0%" y2="100%">
                <stop offset="0%" stop-color="rgba(105, 212, 255, 0.22)" />
                <stop offset="100%" stop-color="rgba(105, 212, 255, 0)" />
              </linearGradient>
            </defs>

            <line
              v-for="grid in 4"
              :key="grid"
              x1="0"
              :y1="grid * 48"
              :x2="chartWidth"
              :y2="grid * 48"
              class="ops-stage-grid"
            />

            <line
              v-if="activeMarkers.crawls"
              :x1="activeMarkers.crawls.x"
              y1="8"
              :x2="activeMarkers.crawls.x"
              :y2="chartHeight - bottomPadding"
              class="ops-stage-guide"
            />

            <path v-if="crawlsPath.area" :d="crawlsPath.area" fill="url(#ops-area-crawls)" />
            <path v-if="crawlsPath.line" :d="crawlsPath.line" class="ops-line ops-line-crawls" />
            <path v-if="successPath.line" :d="successPath.line" class="ops-line ops-line-success" />
            <path v-if="failedPath.line" :d="failedPath.line" class="ops-line ops-line-failed" />

            <circle
              v-if="activeMarkers.crawls"
              :cx="activeMarkers.crawls.x"
              :cy="activeMarkers.crawls.y"
              r="5"
              class="ops-point ops-point-crawls"
            />
            <circle
              v-if="activeMarkers.success"
              :cx="activeMarkers.success.x"
              :cy="activeMarkers.success.y"
              r="5"
              class="ops-point ops-point-success"
            />
            <circle
              v-if="activeMarkers.failed"
              :cx="activeMarkers.failed.x"
              :cy="activeMarkers.failed.y"
              r="5"
              class="ops-point ops-point-failed"
            />
          </svg>

          <transition name="ops-tooltip-fade" mode="out-in">
            <div
              v-if="tooltipStats"
              :key="tooltipStats.date"
              class="ops-stage-tooltip"
              :style="tooltipStyle"
            >
              <header>
                <strong>{{ tooltipStats.date }}</strong>
                <span>成功率 {{ tooltipStats.successRate }}%</span>
              </header>
              <p>总运行 {{ tooltipStats.crawls }} 次</p>
              <p>成功 {{ tooltipStats.success }} 次 / 失败 {{ tooltipStats.failed }} 次</p>
              <p>无新增 {{ tooltipStats.noNew }} 次 / 新增 {{ tooltipStats.newItems }} 条</p>
            </div>
          </transition>

          <div
            v-if="trend.length"
            class="ops-stage-hit-grid"
            :style="{ gridTemplateColumns: `repeat(${trend.length}, minmax(0, 1fr))` }"
          >
            <button
              v-for="(item, index) in trend"
              :key="item.date"
              :class="['ops-stage-hit-zone', { 'is-active': index === safeActiveIndex }]"
              type="button"
              @mouseenter="activeIndex = index"
              @focus="activeIndex = index"
            >
              <span class="ops-stage-sr">
                {{ formatShortDate(item.date) }}：{{ item.crawls }} 次运行，{{ item.failed }} 次失败
              </span>
            </button>
          </div>
        </div>

        <div class="ops-stage-axis">
          <template v-if="chartLabels.length">
            <span v-for="label in chartLabels" :key="label">{{ label }}</span>
          </template>
          <span v-else class="ops-stage-axis-empty">过去 7 天暂无运行数据</span>
        </div>
      </div>

      <div class="ops-stage-summary">
        <article v-for="item in stageSummary" :key="item.label">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <p>{{ item.note }}</p>
        </article>
      </div>
    </div>

    <ServerMetricsPanel :metrics="serverMetrics" :error-message="serverError || ''" />
  </section>
</template>

<style scoped>
.ops-stage {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(320px, 0.9fr);
  gap: 18px;
  padding: 18px;
}

.ops-stage-main {
  display: grid;
  gap: 18px;
  min-width: 0;
  padding: 10px;
}

.ops-stage-head,
.ops-stage-head-meta {
  display: flex;
  justify-content: space-between;
  gap: 18px;
}

.ops-stage-head-meta {
  align-items: flex-start;
}

.ops-stage-head-meta div {
  display: grid;
  gap: 8px;
  min-width: 108px;
  padding: 12px 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.ops-stage-head-meta span,
.ops-stage-subtitle,
.ops-stage-summary span,
.ops-stage-summary p,
.ops-stage-axis span,
.ops-stage-axis-empty,
.ops-stage-legend span,
.ops-stage-focus-copy p,
.ops-stage-focus-label {
  color: var(--muted);
}

.ops-stage-head-meta strong {
  font-size: 22px;
  line-height: 1;
  letter-spacing: -0.04em;
  font-variant-numeric: tabular-nums;
}

.ops-stage-subtitle {
  margin-top: 10px;
  max-width: 640px;
}

.ops-stage-chart-shell {
  display: grid;
  gap: 14px;
  min-width: 0;
  padding: 18px;
  border-radius: 24px;
  background:
    linear-gradient(180deg, rgba(9, 20, 31, 0.88), rgba(8, 16, 24, 0.94)),
    radial-gradient(circle at top left, rgba(105, 212, 255, 0.14), transparent 34%);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.ops-stage-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 12px;
}

.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  margin-right: 8px;
  border-radius: 50%;
}

.legend-crawls {
  background: #69d4ff;
}

.legend-success {
  background: #3dd8a1;
}

.legend-failed {
  background: #ff7f7f;
}

.ops-stage-focus {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.ops-stage-focus-copy {
  display: grid;
  gap: 6px;
  min-width: 150px;
}

.ops-stage-focus-copy strong {
  font-size: 24px;
  line-height: 1;
  letter-spacing: -0.04em;
}

.ops-stage-focus-grid {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.ops-stage-focus-chip {
  display: inline-flex;
  align-items: center;
  padding: 8px 11px;
  border-radius: 999px;
  font-size: 12px;
  color: var(--text);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.ops-stage-focus-chip[data-tone="crawls"] {
  border-color: rgba(105, 212, 255, 0.18);
  background: rgba(105, 212, 255, 0.08);
}

.ops-stage-focus-chip[data-tone="success"] {
  border-color: rgba(61, 216, 161, 0.18);
  background: rgba(61, 216, 161, 0.08);
}

.ops-stage-focus-chip[data-tone="failed"] {
  border-color: rgba(255, 127, 127, 0.18);
  background: rgba(255, 127, 127, 0.08);
}

.ops-stage-plot {
  position: relative;
}

.ops-stage-chart {
  width: 100%;
  height: 240px;
}

.ops-stage-grid {
  stroke: rgba(255, 255, 255, 0.08);
  stroke-dasharray: 4 8;
}

.ops-stage-guide {
  stroke: rgba(255, 255, 255, 0.12);
  stroke-dasharray: 4 8;
}

.ops-line {
  fill: none;
  stroke-width: 3;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.ops-line-crawls {
  stroke: #69d4ff;
}

.ops-line-success {
  stroke: #3dd8a1;
}

.ops-line-failed {
  stroke: #ff7f7f;
}

.ops-point {
  stroke-width: 3;
  fill: var(--bg);
}

.ops-point-crawls {
  stroke: #69d4ff;
}

.ops-point-success {
  stroke: #3dd8a1;
}

.ops-point-failed {
  stroke: #ff7f7f;
}

.ops-stage-hit-grid {
  position: absolute;
  inset: 0 0 28px;
  display: grid;
}

.ops-stage-hit-zone {
  border: 0;
  background: transparent;
  cursor: pointer;
}

.ops-stage-hit-zone.is-active {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent 72%);
}

.ops-stage-tooltip {
  position: absolute;
  z-index: 2;
  min-width: 176px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(105, 212, 255, 0.24);
  background: linear-gradient(180deg, rgba(10, 21, 32, 0.98), rgba(7, 14, 22, 0.98));
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.34);
  transform: translate(-50%, calc(-100% - 10px));
  pointer-events: none;
}

.ops-stage-tooltip header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
  margin-bottom: 6px;
}

.ops-stage-tooltip strong {
  font-size: 13px;
}

.ops-stage-tooltip span,
.ops-stage-tooltip p {
  margin: 0;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.45;
}

.ops-tooltip-fade-enter-active,
.ops-tooltip-fade-leave-active {
  transition: opacity 160ms ease, transform 160ms ease;
}

.ops-tooltip-fade-enter-from,
.ops-tooltip-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, calc(-100% - 6px));
}

.ops-stage-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

.ops-stage-axis {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
  font-size: 11px;
}

.ops-stage-axis span:last-child {
  text-align: right;
}

.ops-stage-axis-empty {
  grid-column: 1 / -1;
}

.ops-stage-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.ops-stage-summary article {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.ops-stage-summary strong {
  font-size: 28px;
  line-height: 1;
  letter-spacing: -0.05em;
}

@media (max-width: 1280px) {
  .ops-stage {
    grid-template-columns: 1fr;
  }

  .ops-stage-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .ops-stage {
    padding: 14px;
  }

  .ops-stage-main,
  .ops-stage-chart-shell {
    padding: 0;
    background: transparent;
    border: 0;
  }

  .ops-stage-head,
  .ops-stage-head-meta,
  .ops-stage-focus {
    flex-direction: column;
  }

  .ops-stage-head-meta {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .ops-stage-focus-grid {
    justify-content: flex-start;
  }

  .ops-stage-axis {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .ops-stage-axis span:nth-child(odd):not(.ops-stage-axis-empty) {
    display: none;
  }

  .ops-stage-summary {
    grid-template-columns: 1fr;
  }
}
</style>
