<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { ApiUsageTrendSeriesItem } from "../types";

const props = defineProps<{
  series: ApiUsageTrendSeriesItem[];
  metric: "cost" | "tokens" | "calls";
}>();

const palette = ["#69d4ff", "#8bffcb", "#ffd479", "#ff9b8a", "#bca2ff", "#9ff0ff"];
const chartWidth = 100;
const chartHeight = 48;
const padding = { top: 5, right: 5, bottom: 8, left: 7 };
const activeDateIndex = ref(0);

function getMetricValue(
  point: ApiUsageTrendSeriesItem["points"][number],
  metric: "cost" | "tokens" | "calls",
) {
  if (metric === "tokens") {
    return point.total_tokens;
  }
  if (metric === "calls") {
    return point.call_count;
  }
  return point.total_cost_usd;
}

const orderedDates = computed(() => {
  const values = new Set<string>();
  for (const item of props.series) {
    for (const point of item.points) {
      values.add(point.date);
    }
  }
  return Array.from(values).sort((a, b) => a.localeCompare(b));
});

watch(
  () => orderedDates.value.length,
  (length) => {
    activeDateIndex.value = length > 0 ? length - 1 : 0;
  },
  { immediate: true },
);

const safeActiveDateIndex = computed(() => {
  const length = orderedDates.value.length;
  if (!length) {
    return 0;
  }
  return Math.max(0, Math.min(activeDateIndex.value, length - 1));
});

const activeDate = computed(() => orderedDates.value[safeActiveDateIndex.value] || null);

const maxValue = computed(() => {
  let currentMax = 0;
  for (const item of props.series) {
    for (const point of item.points) {
      currentMax = Math.max(currentMax, getMetricValue(point, props.metric));
    }
  }
  return currentMax > 0 ? currentMax : 1;
});

const chartSeries = computed(() => {
  const dates = orderedDates.value;
  const spanX = chartWidth - padding.left - padding.right;
  const spanY = chartHeight - padding.top - padding.bottom;

  return props.series.map((item, index) => {
    const pointMap = new Map(item.points.map((point) => [point.date, point]));
    const points = dates.map((date, dateIndex) => {
      const raw = pointMap.get(date);
      const value = raw ? getMetricValue(raw, props.metric) : 0;
      const x = dates.length <= 1 ? padding.left : padding.left + (spanX * dateIndex) / (dates.length - 1);
      const y = padding.top + spanY - (value / maxValue.value) * spanY;
      return {
        date,
        value,
        x,
        y,
      };
    });

    return {
      key: item.system,
      label: item.system_label || item.system,
      color: palette[index % palette.length],
      total: points.reduce((sum, point) => sum + point.value, 0),
      lastValue: points.length ? points[points.length - 1].value : 0,
      path: points
        .map((point, pointIndex) => `${pointIndex === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
        .join(" "),
      points,
    };
  });
});

const activeX = computed(() => {
  const firstSeries = chartSeries.value[0];
  if (!firstSeries || !firstSeries.points.length) {
    return padding.left;
  }
  const point = firstSeries.points[safeActiveDateIndex.value];
  return point ? point.x : padding.left;
});

const focusRows = computed(() => {
  const index = safeActiveDateIndex.value;
  return chartSeries.value
    .map((item) => ({
      key: item.key,
      label: item.label,
      color: item.color,
      value: item.points[index]?.value || 0,
    }))
    .sort((left, right) => right.value - left.value);
});

const gridLines = computed(() => {
  const spanY = chartHeight - padding.top - padding.bottom;
  return [1, 0.5, 0].map((ratio) => ({
    y: padding.top + spanY - spanY * ratio,
    value: maxValue.value * ratio,
  }));
});

const tooltipStyle = computed(() => {
  const clampedLeft = Math.max(14, Math.min(chartWidth - 14, activeX.value));
  return {
    left: `${clampedLeft}%`,
    top: `${padding.top + 1}%`,
  };
});

function formatDateLabel(value: string | null) {
  if (!value) {
    return "--";
  }
  return value.length >= 10 ? value.slice(5) : value;
}

function formatAxisValue(value: number) {
  if (props.metric === "cost") {
    return `$${value.toFixed(value < 1 ? 3 : 2)}`;
  }
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}k`;
  }
  return `${Math.round(value)}`;
}

function formatMetricValue(value: number) {
  if (props.metric === "cost") {
    return `$${value.toFixed(4)}`;
  }
  return Intl.NumberFormat("zh-CN").format(Math.round(value));
}

function formatLegendValue(value: number) {
  if (props.metric === "cost") {
    return `$${value.toFixed(4)}`;
  }
  return Intl.NumberFormat("zh-CN").format(Math.round(value));
}
</script>

<template>
  <div class="api-trend-chart">
    <div v-if="!chartSeries.length || !orderedDates.length" class="api-trend-empty">当前时间窗暂无跨系统趋势数据</div>

    <template v-else>
      <div class="api-trend-focus">
        <div class="api-trend-focus-head">
          <span>焦点日期</span>
          <strong>{{ formatDateLabel(activeDate) }}</strong>
        </div>
        <div class="api-trend-focus-grid">
          <span
            v-for="item in focusRows"
            :key="`focus-${item.key}`"
            class="api-trend-focus-chip"
            :style="{ '--chip-color': item.color }"
          >
            {{ item.label }} {{ formatMetricValue(item.value) }}
          </span>
        </div>
      </div>

      <div class="api-trend-plot">
        <svg
          class="api-trend-svg"
          :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
          preserveAspectRatio="none"
          role="img"
          aria-label="跨系统 API 使用趋势图"
        >
          <g class="api-trend-grid">
            <line
              v-for="line in gridLines"
              :key="line.y"
              :x1="padding.left"
              :x2="chartWidth - padding.right"
              :y1="line.y"
              :y2="line.y"
            />
          </g>

          <line
            class="api-trend-guide"
            :x1="activeX"
            :x2="activeX"
            :y1="padding.top"
            :y2="chartHeight - padding.bottom"
          />

          <g class="api-trend-axis-labels">
            <text
              v-for="line in gridLines"
              :key="`label-${line.y}`"
              :x="0"
              :y="line.y + 1"
            >
              {{ formatAxisValue(line.value) }}
            </text>
          </g>

          <g v-for="item in chartSeries" :key="item.key">
            <path :d="item.path" :stroke="item.color" class="api-trend-line" />
            <circle
              v-for="(point, index) in item.points"
              :key="`${item.key}-${point.date}`"
              :cx="point.x"
              :cy="point.y"
              :fill="item.color"
              class="api-trend-point"
              :class="{ 'is-active': index === safeActiveDateIndex }"
              :r="index === safeActiveDateIndex ? 0.95 : 0.62"
            >
              <title>{{ `${item.label} ${point.date}: ${formatLegendValue(point.value)}` }}</title>
            </circle>
          </g>

          <g class="api-trend-dates">
            <text
              v-for="date in [orderedDates[0], orderedDates[Math.floor((orderedDates.length - 1) / 2)], orderedDates[orderedDates.length - 1]].filter(Boolean)"
              :key="date"
              :x="orderedDates.length <= 1 ? chartWidth / 2 : padding.left + ((chartWidth - padding.left - padding.right) * orderedDates.indexOf(date)) / (orderedDates.length - 1)"
              :y="chartHeight - 1"
              text-anchor="middle"
            >
              {{ date.slice(5) }}
            </text>
          </g>
        </svg>

        <transition name="api-trend-tooltip-fade" mode="out-in">
          <div
            v-if="activeDate"
            :key="activeDate"
            class="api-trend-tooltip"
            :style="tooltipStyle"
          >
            <header>
              <strong>{{ formatDateLabel(activeDate) }}</strong>
            </header>
            <p v-for="item in focusRows" :key="`tip-${item.key}`">
              <i :style="{ backgroundColor: item.color }"></i>
              <span>{{ item.label }}</span>
              <b>{{ formatMetricValue(item.value) }}</b>
            </p>
          </div>
        </transition>

        <div
          class="api-trend-hit-grid"
          :style="{ gridTemplateColumns: `repeat(${orderedDates.length}, minmax(0, 1fr))` }"
        >
          <button
            v-for="(date, index) in orderedDates"
            :key="`hit-${date}`"
            :class="['api-trend-hit-zone', { 'is-active': index === safeActiveDateIndex }]"
            type="button"
            @mouseenter="activeDateIndex = index"
            @focus="activeDateIndex = index"
          >
            <span class="api-trend-sr">{{ formatDateLabel(date) }}</span>
          </button>
        </div>
      </div>

      <div class="api-trend-legend">
        <article v-for="item in chartSeries" :key="`legend-${item.key}`" class="api-trend-legend-item">
          <span class="api-trend-swatch" :style="{ backgroundColor: item.color }"></span>
          <div>
            <strong>{{ item.label }}</strong>
            <small>末值 {{ formatLegendValue(item.lastValue) }} / 累计 {{ formatLegendValue(item.total) }}</small>
          </div>
        </article>
      </div>
    </template>
  </div>
</template>

<style scoped>
.api-trend-chart {
  display: grid;
  gap: 10px;
}

.api-trend-empty {
  min-height: 180px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  border: 1px dashed rgba(126, 148, 171, 0.26);
  color: var(--muted);
  background: rgba(255, 255, 255, 0.015);
}

.api-trend-focus {
  display: grid;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.04);
}

.api-trend-focus-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.api-trend-focus-head span {
  color: var(--muted);
  font-size: 12px;
}

.api-trend-focus-head strong {
  font-size: 14px;
  letter-spacing: 0.03em;
}

.api-trend-focus-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.api-trend-focus-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 7px;
  border-radius: 999px;
  font-size: 11px;
  color: rgba(235, 244, 252, 0.92);
  background: color-mix(in srgb, var(--chip-color) 14%, rgba(255, 255, 255, 0.03));
  border: 1px solid color-mix(in srgb, var(--chip-color) 35%, rgba(255, 255, 255, 0.08));
}

.api-trend-plot {
  position: relative;
}

.api-trend-svg {
  width: 100%;
  min-height: 150px;
  overflow: visible;
}

.api-trend-grid line {
  stroke: rgba(255, 255, 255, 0.08);
  stroke-dasharray: 2 3;
}

.api-trend-guide {
  stroke: rgba(147, 220, 255, 0.38);
  stroke-width: 0.34;
  stroke-dasharray: 1.2 1.2;
}

.api-trend-axis-labels text,
.api-trend-dates text {
  fill: rgba(222, 233, 244, 0.56);
  font-size: 3px;
}

.api-trend-line {
  fill: none;
  stroke-width: 1.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.api-trend-point {
  opacity: 0.65;
  transition: r 0.2s ease, opacity 0.2s ease;
}

.api-trend-point.is-active {
  opacity: 1;
}

.api-trend-hit-grid {
  position: absolute;
  inset: 6% 6% 18% 8%;
  display: grid;
  z-index: 5;
}

.api-trend-hit-zone {
  border: 0;
  background: transparent;
  cursor: pointer;
}

.api-trend-hit-zone.is-active {
  background: linear-gradient(to bottom, rgba(130, 189, 255, 0.08), rgba(130, 189, 255, 0));
}

.api-trend-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

.api-trend-tooltip {
  position: absolute;
  z-index: 8;
  transform: translateX(-50%);
  min-width: 148px;
  max-width: 190px;
  padding: 6px 8px;
  border-radius: 8px;
  border: 1px solid rgba(113, 164, 208, 0.32);
  background: rgba(8, 19, 34, 0.92);
  box-shadow: 0 10px 24px rgba(1, 7, 16, 0.45);
  pointer-events: none;
}

.api-trend-tooltip header {
  margin-bottom: 6px;
}

.api-trend-tooltip strong {
  font-size: 11px;
}

.api-trend-tooltip p {
  margin: 0;
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  align-items: center;
  column-gap: 6px;
  font-size: 10px;
  line-height: 1.45;
  color: rgba(218, 231, 245, 0.9);
}

.api-trend-tooltip i {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  display: inline-block;
}

.api-trend-tooltip span {
  color: rgba(218, 231, 245, 0.8);
}

.api-trend-tooltip b {
  color: rgba(238, 247, 255, 0.98);
}

.api-trend-tooltip-fade-enter-active,
.api-trend-tooltip-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.api-trend-tooltip-fade-enter-from,
.api-trend-tooltip-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, 6px);
}

.api-trend-legend {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}

.api-trend-legend-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.04);
}

.api-trend-legend-item strong,
.api-trend-legend-item small {
  display: block;
}

.api-trend-legend-item small {
  margin-top: 4px;
  color: var(--muted);
}

.api-trend-swatch {
  width: 10px;
  height: 10px;
  margin-top: 5px;
  border-radius: 999px;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.04);
}

@media (max-width: 760px) {
  .api-trend-svg {
    min-height: 165px;
  }

  .api-trend-tooltip {
    min-width: 132px;
    max-width: 160px;
  }

  .api-trend-legend {
    grid-template-columns: 1fr;
  }
}
</style>
