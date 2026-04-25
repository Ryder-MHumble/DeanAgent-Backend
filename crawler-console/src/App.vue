<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { consoleApi } from "./api/console";
import ApiUsageTrendChart from "./components/ApiUsageTrendChart.vue";
import DarkSelect from "./components/DarkSelect.vue";
import IntelDock from "./components/IntelDock.vue";
import OpsStage from "./components/OpsStage.vue";
import SourceDrawer from "./components/SourceDrawer.vue";
import SourceTable from "./components/SourceTable.vue";
import SystemNav from "./components/SystemNav.vue";
import { useConsoleController } from "./composables/useConsoleController";
import { useWorkspaceNavigation, type SectionId } from "./composables/useWorkspaceNavigation";
import { formatDateTime, formatNumber } from "./utils/consoleFormat";

interface MetricTile {
  label: string;
  value: number | string;
  hint: string;
  tone?: "default" | "warning";
}

interface SelectOption {
  label: string;
  value: string | number;
}

type ApiTrendMetric = "cost" | "tokens" | "calls";

const {
  activeSource,
  allVisibleSelected,
  canNextPage,
  canPrevPage,
  clearFilters,
  clearSelection,
  closeDrawer,
  currentPage,
  drawerOpen,
  errorMessage,
  filters,
  goNextPage,
  goPrevPage,
  inspectSource,
  isRefreshing,
  lastAction,
  logsLoading,
  manualActionLoading,
  manualForm,
  overview,
  refreshAll: refreshConsoleData,
  serverMetrics,
  serverMetricsError,
  apiUsage,
  apiUsageLoading,
  apiUsageError,
  apiUsageFilters,
  selectedCount,
  selectedSourceId,
  selectedSourceIds,
  selectAllFiltered,
  selectAllFilteredLoading,
  sourceCatalog,
  sourceLoading,
  sourceLogs,
  sources,
  startManualJob,
  statusMessage,
  stopManualJob,
  toggleAllVisible,
  toggleSelect,
  toggleSource,
  togglingSourceIds,
  totalPages,
  trend,
  triggerSource,
  triggeringSourceIds,
} = useConsoleController();

const {
  activeSection,
  intelTab,
  navigateToSection,
  openBatchPanel,
  workspaceMainTab,
  workspaceSideTab,
} = useWorkspaceNavigation();

const monitorTab = ref<"crawler" | "api">("crawler");
const apiMetric = ref<ApiTrendMetric>("cost");

async function handleSectionNavigate(section: SectionId) {
  monitorTab.value = section === "api" ? "api" : "crawler";
  await nextTick();
  await navigateToSection(section);
}

async function openBatchWorkspace() {
  monitorTab.value = "crawler";
  await nextTick();
  await openBatchPanel();
}

async function refreshAll() {
  await refreshConsoleData();
}

const manualProgressPercent = computed(() =>
  Math.round((overview.value?.manual_job.progress || 0) * 100),
);

const metricTiles = computed<MetricTile[]>(() => {
  if (!overview.value) {
    return [];
  }

  const { health, today, manual_job } = overview.value;
  return [
    { label: "总信源", value: health.total_sources, hint: `${health.enabled_sources} 已启用` },
    { label: "健康信源", value: health.healthy, hint: `${health.warning} 告警 / ${health.failing} 失败` },
    { label: "今日运行", value: today.total_runs, hint: `${today.successful_runs} 成功 / ${today.failed_runs} 失败` },
    { label: "今日新增", value: today.new_items, hint: `${today.total_items} 条解析结果` },
    {
      label: "手动任务",
      value: manual_job.is_running ? `${manualProgressPercent.value}%` : "空闲",
      hint: manual_job.is_running
        ? `${manual_job.completed_count}/${manual_job.requested_source_count} 执行中`
        : manual_job.result_file_name || "等待任务",
      tone: manual_job.is_running ? "warning" : "default",
    },
  ];
});

const hasActiveFilters = computed(
  () =>
    Boolean(filters.keyword.trim()) ||
    Boolean(filters.dimension) ||
    Boolean(filters.health_status) ||
    filters.is_enabled !== "",
);

const feedbackTone = computed(() => {
  if (errorMessage.value) {
    return "is-error";
  }
  if (lastAction.value) {
    return "is-success";
  }
  return "";
});

const feedbackMessage = computed(() => errorMessage.value || lastAction.value || statusMessage.value);
const filterResultSummary = computed(
  () => `筛选结果 ${sourceCatalog.value?.filtered_sources || 0} / ${sourceCatalog.value?.total_sources || 0}`,
);
const selectAllFilteredLabel = computed(() => {
  if (selectAllFilteredLoading.value) {
    return "跨页选择中...";
  }
  return `全选筛选结果（${sourceCatalog.value?.filtered_sources || 0}）`;
});
const selectionCoverageHint = computed(() => {
  const filtered = sourceCatalog.value?.filtered_sources || 0;
  if (!filtered) {
    return "完成筛选与勾选后，可直接进入批量执行面板。";
  }

  if (
    filtered > selectedCount.value &&
    selectedCount.value > 0 &&
    selectedCount.value === sources.value.length &&
    allVisibleSelected.value
  ) {
    return `当前仅选中本页 ${selectedCount.value} 条，启动批量任务时会自动扩展到筛选命中的 ${filtered} 条。`;
  }

  if (selectedCount.value > 0 && filtered > selectedCount.value) {
    return `当前已选 ${selectedCount.value} / ${filtered} 条信源。`;
  }

  return "完成筛选与勾选后，可直接进入批量执行面板。";
});
const batchPrimaryLabel = computed(() => {
  if (!selectedCount.value) {
    return "先在主表勾选信源";
  }
  return manualActionLoading.value ? "提交中..." : "③ 启动批量任务";
});
const refreshCadenceText = computed(() => "10 秒");
const tableScope = computed(() => {
  if (filters.health_status === "failing") {
    return "failing";
  }
  if (filters.health_status === "warning") {
    return "warning";
  }
  if (filters.is_enabled === "true") {
    return "enabled";
  }
  if (filters.is_enabled === "false") {
    return "disabled";
  }
  return "all";
});

watch(
  () => overview.value?.manual_job.is_running,
  (running) => {
    if (running) {
      intelTab.value = "manual";
      return;
    }

    if (intelTab.value === "manual") {
      intelTab.value = "runs";
    }
  },
  { immediate: true },
);

function applyTableScope(mode: "all" | "enabled" | "disabled" | "warning" | "failing") {
  if (mode === "all") {
    filters.health_status = "";
    filters.is_enabled = "";
    return;
  }
  if (mode === "enabled") {
    filters.is_enabled = "true";
    filters.health_status = "";
    return;
  }
  if (mode === "disabled") {
    filters.is_enabled = "false";
    filters.health_status = "";
    return;
  }
  filters.is_enabled = "";
  filters.health_status = mode;
}

const apiOverview = computed(() =>
  apiUsage.value?.overview || {
    total_calls: 0,
    success_calls: 0,
    failed_calls: 0,
    success_rate: 0,
    total_input_tokens: 0,
    total_output_tokens: 0,
    total_tokens: 0,
    total_cost_usd: 0,
    priced_calls: 0,
    unpriced_calls: 0,
    unpriced_tokens: 0,
    avg_cost_per_call_usd: 0,
  },
);

const apiFilterOptions = computed(() =>
  apiUsage.value?.available_filters || {
    systems: [],
    modules: [],
    stages: [],
    models: [],
    source_ids: [],
  },
);

const apiTimeWindowOptions: SelectOption[] = [
  { label: "1 天", value: 1 },
  { label: "7 天", value: 7 },
  { label: "30 天", value: 30 },
];

const apiSuccessOptions: SelectOption[] = [
  { label: "全部", value: "all" },
  { label: "成功", value: "success" },
  { label: "失败", value: "failed" },
];

const apiMetricOptions: Array<{ label: string; value: ApiTrendMetric }> = [
  { label: "费用", value: "cost" },
  { label: "Token", value: "tokens" },
  { label: "调用", value: "calls" },
];

const apiSystemLabelMap = computed(() => {
  const map = new Map<string, string>();
  for (const item of apiUsage.value?.by_system || []) {
    if (item.system_label) {
      map.set(item.system, item.system_label);
    }
  }
  for (const item of apiUsage.value?.trend_series || []) {
    if (item.system_label) {
      map.set(item.system, item.system_label);
    }
  }
  return map;
});

const apiSystemOptions = computed<SelectOption[]>(() => [
  { label: "全部系统", value: "" },
  ...apiFilterOptions.value.systems.map((item) => ({
    label: apiSystemLabelMap.value.get(item) || item,
    value: item,
  })),
]);

const apiModuleOptions = computed<SelectOption[]>(() => [
  { label: "全部模块", value: "" },
  ...apiFilterOptions.value.modules.map((item) => ({ label: item, value: item })),
]);

const apiStageOptions = computed<SelectOption[]>(() => [
  { label: "全部 stage", value: "" },
  ...apiFilterOptions.value.stages.map((item) => ({ label: item, value: item })),
]);

const apiModelOptions = computed<SelectOption[]>(() => [
  { label: "全部模型", value: "" },
  ...apiFilterOptions.value.models.map((item) => ({ label: item, value: item })),
]);

const apiBySystem = computed(() => (apiUsage.value?.by_system || []).slice(0, 8));
const apiByModule = computed(() => (apiUsage.value?.by_module || []).slice(0, 8));
const apiByModel = computed(() => (apiUsage.value?.by_model || []).slice(0, 8));
const apiRecentCalls = computed(() => apiUsage.value?.recent_calls || []);
const apiGeneratedAtText = computed(() => formatDateTime(apiUsage.value?.generated_at || null));
const apiActiveSystems = computed(() =>
  (apiUsage.value?.by_system || []).filter((item) => item.call_count > 0).length,
);
const apiSystemLead = computed(() => apiBySystem.value[0] || null);
const apiMetricLabel = computed(() => apiMetricOptions.find((item) => item.value === apiMetric.value)?.label || "费用");
const apiCurrentSystemLabel = computed(() => {
  const currentSystem = apiUsage.value?.scope.system || apiUsageFilters.system || "";
  if (!currentSystem) {
    return "全部系统";
  }

  const matchedSystem =
    apiUsage.value?.by_system?.find((item) => item.system === currentSystem)?.system_label ||
    apiUsage.value?.trend_series?.find((item) => item.system === currentSystem)?.system_label;

  return matchedSystem || currentSystem;
});

const apiTrendSeries = computed(() =>
  (apiUsage.value?.trend_series || [])
    .filter((item) => item.points.length)
    .map((item) => {
      const totalMetric = item.points.reduce((sum, point) => {
        if (apiMetric.value === "tokens") {
          return sum + point.total_tokens;
        }
        if (apiMetric.value === "calls") {
          return sum + point.call_count;
        }
        return sum + point.total_cost_usd;
      }, 0);

      return {
        item,
        totalMetric,
      };
    })
    .sort((left, right) => right.totalMetric - left.totalMetric)
    .slice(0, 6)
    .map(({ item }) => item),
);

const apiScopeSummary = computed(() => {
  const parts = [`近 ${apiUsageFilters.days} 天`, apiCurrentSystemLabel.value];

  if (apiUsageFilters.module) {
    parts.push(`模块 ${apiUsageFilters.module}`);
  }
  if (apiUsageFilters.stage) {
    parts.push(`Stage ${apiUsageFilters.stage}`);
  }
  if (apiUsageFilters.model) {
    parts.push(`模型 ${apiUsageFilters.model}`);
  }
  if (apiUsageFilters.source_id.trim()) {
    parts.push(`Source ${apiUsageFilters.source_id.trim()}`);
  }
  if (apiUsageFilters.success !== "all") {
    parts.push(apiUsageFilters.success === "success" ? "仅成功调用" : "仅失败调用");
  }

  return parts.join(" / ");
});

const apiUnpricedRatio = computed(() => {
  const total = apiOverview.value.total_calls || 0;
  if (!total) {
    return 0;
  }
  return (apiOverview.value.unpriced_calls / total) * 100;
});

const apiHasFilters = computed(
  () =>
    apiUsageFilters.days !== 7 ||
    Boolean(apiUsageFilters.system) ||
    Boolean(apiUsageFilters.module) ||
    Boolean(apiUsageFilters.stage) ||
    Boolean(apiUsageFilters.model) ||
    Boolean(apiUsageFilters.source_id) ||
    apiUsageFilters.success !== "all",
);

function formatUsd(value: number | null | undefined, digits = 4) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  return `$${value.toFixed(digits)}`;
}

function formatApiCallCost(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "未定价";
  }
  return formatUsd(value, 6);
}

function formatDurationMs(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  if (value < 1000) {
    return `${Math.round(value)}ms`;
  }
  return `${(value / 1000).toFixed(2)}s`;
}

function clearApiFilters() {
  apiUsageFilters.days = 7;
  apiUsageFilters.system = "";
  apiUsageFilters.module = "";
  apiUsageFilters.stage = "";
  apiUsageFilters.model = "";
  apiUsageFilters.source_id = "";
  apiUsageFilters.success = "all";
}
</script>

<template>
  <div class="console-shell">
    <SystemNav
      :active-section="activeSection"
      :scheduler-status="overview?.scheduler_status || null"
      :generated-at="overview?.generated_at || null"
      @navigate="handleSectionNavigate"
    />

    <main class="console-main">
      <header id="section-overview" class="command-header panel">
        <div class="command-copy">
          <p class="eyebrow">Dean Control Tower</p>
          <h1>情报引擎数据控制台</h1>
          <p class="subtitle">以信源主表为中心，把运行趋势、服务器负载、筛选编排和任务动作收进同一块工作台。</p>
        </div>

        <div class="command-actions">
          <div class="monitor-switch monitor-switch--inline" aria-label="监控视图切换">
            <button
              :class="['workspace-tab', { 'is-active': monitorTab === 'crawler' }]"
              type="button"
              @click="handleSectionNavigate('ops')"
            >
              爬虫监控
            </button>
            <button
              :class="['workspace-tab', { 'is-active': monitorTab === 'api' }]"
              type="button"
              @click="handleSectionNavigate('api')"
            >
              API 监控
            </button>
          </div>
          <div class="command-state">
            <span class="meta-label">调度状态</span>
            <span class="status-pill" :data-status="overview?.scheduler_status === 'running' ? 'healthy' : 'unknown'">
              {{ overview?.scheduler_status === "running" ? "运行中" : "未启动" }}
            </span>
          </div>
          <div class="command-state">
            <span class="meta-label">最近同步</span>
            <strong>{{ formatDateTime(overview?.generated_at || null) }}</strong>
          </div>
          <button class="accent-button" type="button" :disabled="isRefreshing" @click="refreshAll">
            {{ isRefreshing ? "同步中..." : "刷新面板" }}
          </button>
        </div>

        <div :class="['header-feedback', feedbackTone]" role="status" aria-live="polite">
          {{ feedbackMessage }}
        </div>
      </header>

      <section id="section-ops" v-show="monitorTab === 'crawler'">
        <OpsStage
          :overview="overview"
          :trend="trend"
          :server-metrics="serverMetrics"
          :server-error="serverMetricsError"
        />
      </section>

      <section id="section-api" class="api-monitor panel" v-show="monitorTab === 'api'">
        <header class="api-monitor-head">
          <div class="api-monitor-copy">
            <p class="eyebrow">OpenRouter Usage</p>
            <h2>API 监控</h2>
            <p class="panel-note">按系统、模块、模型和最近调用明细重排工作面，优先暴露跨系统费用变化与资源占用。</p>
          </div>
          <div class="api-monitor-meta">
            <span class="meta-label">数据时间</span>
            <strong>{{ apiGeneratedAtText }}</strong>
            <small>{{ apiScopeSummary }}</small>
          </div>
        </header>

        <section class="api-filter-shell" aria-label="API 筛选器">
          <div class="api-filter-bar">
            <label>
              <span>时间窗</span>
              <DarkSelect v-model="apiUsageFilters.days" :options="apiTimeWindowOptions" />
            </label>
            <label>
              <span>系统</span>
              <DarkSelect v-model="apiUsageFilters.system" :options="apiSystemOptions" />
            </label>
            <label>
              <span>模块</span>
              <DarkSelect v-model="apiUsageFilters.module" :options="apiModuleOptions" />
            </label>
            <label>
              <span>Stage</span>
              <DarkSelect v-model="apiUsageFilters.stage" :options="apiStageOptions" />
            </label>
            <label>
              <span>模型</span>
              <DarkSelect v-model="apiUsageFilters.model" :options="apiModelOptions" />
            </label>
            <label>
              <span>状态</span>
              <DarkSelect v-model="apiUsageFilters.success" :options="apiSuccessOptions" />
            </label>
            <label class="api-filter-source">
              <span>Source</span>
              <input v-model="apiUsageFilters.source_id" type="text" list="api-source-options" placeholder="输入 source_id" />
              <datalist id="api-source-options">
                <option v-for="item in apiFilterOptions.source_ids" :key="item" :value="item"></option>
              </datalist>
            </label>
          </div>

          <div class="api-filter-actions">
            <p class="api-filter-summary">{{ apiScopeSummary }}</p>
            <button class="ghost-button api-reset-button" type="button" :disabled="!apiHasFilters" @click="clearApiFilters">
              重置筛选
            </button>
          </div>
        </section>

        <p v-if="apiUsageError" class="api-error" role="alert">{{ apiUsageError }}</p>
        <p v-else-if="!apiUsageLoading && !apiOverview.total_calls" class="api-empty-note">当前时间窗没有 OpenRouter 调用记录，可先运行带 LLM 的爬虫或检查 llm_provider 配置。</p>

        <div class="api-kpi-grid">
          <article class="api-kpi-item">
            <span class="kpi-label">总调用</span>
            <strong class="kpi-value">{{ formatNumber(apiOverview.total_calls) }}</strong>
            <span class="kpi-hint">成功 {{ formatNumber(apiOverview.success_calls) }} / 失败 {{ formatNumber(apiOverview.failed_calls) }}</span>
          </article>
          <article class="api-kpi-item">
            <span class="kpi-label">总 Token</span>
            <strong class="kpi-value">{{ formatNumber(apiOverview.total_tokens) }}</strong>
            <span class="kpi-hint">输入 {{ formatNumber(apiOverview.total_input_tokens) }} / 输出 {{ formatNumber(apiOverview.total_output_tokens) }}</span>
          </article>
          <article class="api-kpi-item">
            <span class="kpi-label">总费用</span>
            <strong class="kpi-value">{{ formatUsd(apiOverview.total_cost_usd, 6) }}</strong>
            <span class="kpi-hint">按已定价调用累计</span>
          </article>
          <article class="api-kpi-item">
            <span class="kpi-label">成功率</span>
            <strong class="kpi-value">{{ apiOverview.success_rate.toFixed(1) }}%</strong>
            <span class="kpi-hint">均次成本 {{ formatUsd(apiOverview.avg_cost_per_call_usd, 6) }}</span>
          </article>
          <article class="api-kpi-item">
            <span class="kpi-label">活跃系统</span>
            <strong class="kpi-value">{{ formatNumber(apiActiveSystems) }}</strong>
            <span class="kpi-hint">当前范围 {{ apiCurrentSystemLabel }}</span>
          </article>
          <article class="api-kpi-item">
            <span class="kpi-label">未定价占比</span>
            <strong class="kpi-value">{{ apiUnpricedRatio.toFixed(1) }}%</strong>
            <span class="kpi-hint">{{ formatNumber(apiOverview.unpriced_calls) }} / {{ formatNumber(apiOverview.total_calls) }} 调用</span>
          </article>
        </div>

        <div class="api-layout-grid">
          <article class="api-panel-card api-trend-panel">
            <header class="api-subhead api-subhead--stretch">
              <div>
                <h3>跨系统消耗趋势</h3>
                <span class="panel-note">按 {{ apiMetricLabel }} 对比不同系统在时间窗内的变化，仅展示前 {{ formatNumber(apiTrendSeries.length) }} 个系统</span>
              </div>
              <div class="api-metric-toggle" role="tablist" aria-label="趋势指标切换">
                <button
                  v-for="item in apiMetricOptions"
                  :key="item.value"
                  :class="['workspace-tab', 'api-metric-tab', { 'is-active': apiMetric === item.value }]"
                  type="button"
                  @click="apiMetric = item.value"
                >
                  {{ item.label }}
                </button>
              </div>
            </header>
            <ApiUsageTrendChart :series="apiTrendSeries" :metric="apiMetric" />
          </article>

          <article class="api-panel-card api-system-panel">
            <header class="api-subhead">
              <div>
                <h3>系统排行</h3>
                <span class="panel-note">system / 调用 / token / 费用 / 成功率</span>
              </div>
            </header>

            <div v-if="apiSystemLead" class="api-system-highlight">
              <span class="api-system-highlight-kicker">费用最高系统</span>
              <strong>{{ apiSystemLead.system_label || apiSystemLead.system }}</strong>
              <div class="api-system-highlight-stats">
                <span>调用 {{ formatNumber(apiSystemLead.call_count) }}</span>
                <span>Token {{ formatNumber(apiSystemLead.total_tokens) }}</span>
                <span>费用 {{ formatUsd(apiSystemLead.total_cost_usd, 6) }}</span>
              </div>
            </div>

            <div class="api-table-wrap">
              <table class="api-table api-system-table">
                <thead>
                  <tr>
                    <th>System</th>
                    <th>调用</th>
                    <th>Token</th>
                    <th>费用(USD)</th>
                    <th>成功率</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in apiBySystem" :key="row.system">
                    <td>{{ row.system_label || row.system }}</td>
                    <td>{{ formatNumber(row.call_count) }}</td>
                    <td>{{ formatNumber(row.total_tokens) }}</td>
                    <td>{{ formatUsd(row.total_cost_usd, 6) }}</td>
                    <td>{{ row.success_rate.toFixed(1) }}%</td>
                  </tr>
                  <tr v-if="!apiBySystem.length">
                    <td colspan="5" class="section-empty">暂无系统维度统计</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>

          <article class="api-panel-card api-rank-card">
            <header class="api-subhead">
              <div>
                <h3>模块排行</h3>
                <span class="panel-note">按费用 / Token / 调用量排序</span>
              </div>
            </header>
            <div class="api-table-wrap">
              <table class="api-table">
                <thead>
                  <tr>
                    <th>模块</th>
                    <th>调用</th>
                    <th>Token</th>
                    <th>费用(USD)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in apiByModule" :key="row.module">
                    <td>{{ row.module }}</td>
                    <td>{{ formatNumber(row.call_count) }}</td>
                    <td>{{ formatNumber(row.total_tokens) }}</td>
                    <td>{{ formatUsd(row.total_cost_usd, 6) }}</td>
                  </tr>
                  <tr v-if="!apiByModule.length">
                    <td colspan="4" class="section-empty">暂无模块统计</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>

          <article class="api-panel-card api-rank-card">
            <header class="api-subhead">
              <div>
                <h3>模型排行</h3>
                <span class="panel-note">调用 / Token / 费用 / 均次成本</span>
              </div>
            </header>
            <div class="api-table-wrap">
              <table class="api-table">
                <thead>
                  <tr>
                    <th>模型</th>
                    <th>调用</th>
                    <th>Token</th>
                    <th>费用(USD)</th>
                    <th>均次成本</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in apiByModel" :key="row.model">
                    <td>{{ row.model }}</td>
                    <td>{{ formatNumber(row.call_count) }}</td>
                    <td>{{ formatNumber(row.total_tokens) }}</td>
                    <td>{{ formatUsd(row.total_cost_usd, 6) }}</td>
                    <td>{{ row.priced_calls ? formatUsd(row.avg_cost_per_call_usd, 6) : "--" }}</td>
                  </tr>
                  <tr v-if="!apiByModel.length">
                    <td colspan="5" class="section-empty">暂无模型统计</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>

          <section class="api-panel-card api-recent-card api-recent-panel">
            <header class="api-subhead">
              <div>
                <h3>最近调用明细</h3>
                <span class="panel-note">展示最近 {{ formatNumber(apiRecentCalls.length) }} 条，按时间倒序</span>
              </div>
            </header>
            <div class="api-table-wrap">
              <table class="api-table api-recent-table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>系统</th>
                    <th>模块</th>
                    <th>Stage</th>
                    <th>模型</th>
                    <th>Source</th>
                    <th>Token</th>
                    <th>费用</th>
                    <th>状态</th>
                    <th>耗时</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="call in apiRecentCalls" :key="`${call.timestamp}-${call.stage}-${call.article_id || ''}`">
                    <td>{{ formatDateTime(call.timestamp) }}</td>
                    <td>{{ call.system_label || call.system }}</td>
                    <td>{{ call.module }}</td>
                    <td>{{ call.stage }}</td>
                    <td>{{ call.model }}</td>
                    <td>{{ call.source_id || call.article_id || "-" }}</td>
                    <td>{{ formatNumber(call.total_tokens) }}</td>
                    <td>
                      <span :class="['api-cost-tag', { 'is-unpriced': call.effective_cost_usd === null }]">
                        {{ formatApiCallCost(call.effective_cost_usd) }}
                      </span>
                      <small class="api-cost-source">{{ call.cost_source }}</small>
                    </td>
                    <td>
                      <span class="status-pill" :data-status="call.success ? 'success' : 'failed'">
                        {{ call.success ? "成功" : "失败" }}
                      </span>
                    </td>
                    <td>{{ formatDurationMs(call.duration_ms) }}</td>
                  </tr>
                  <tr v-if="!apiRecentCalls.length">
                    <td colspan="10" class="section-empty">
                      {{ apiUsageLoading ? "API 监控加载中..." : "最近时间窗内暂无调用记录" }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </section>
      <section class="kpi-band panel" v-show="monitorTab === 'crawler'">
        <article
          v-for="tile in metricTiles"
          :key="tile.label"
          :class="['kpi-cell', { 'is-warning': tile.tone === 'warning' }]"
        >
          <span class="kpi-label">{{ tile.label }}</span>
          <strong class="kpi-value">{{ formatNumber(tile.value) }}</strong>
          <span class="kpi-hint">{{ tile.hint }}</span>
        </article>
      </section>

      <section id="section-sources" class="workspace-shell" v-show="monitorTab === 'crawler'">
        <div class="workspace-main-column">
          <section class="workspace-head panel">
            <div class="workspace-head-copy">
              <p class="eyebrow">Workbench</p>
              <h2>信源工作台</h2>
              <p class="panel-note">只保留一条主路径：筛选 -> 勾选 -> 批量执行，减少跳读和误触。</p>
              <div class="workspace-flow-hint" role="note" aria-label="操作引导">
                <span><strong>1.</strong> 搜索筛选</span>
                <span><strong>2.</strong> 勾选信源</span>
                <span><strong>3.</strong> 启动批量任务</span>
              </div>
            </div>
            <div class="workspace-main-tabs" role="tablist" aria-label="主工作区视图">
              <button
                :class="['workspace-tab', { 'is-active': workspaceMainTab === 'ledger' }]"
                type="button"
                role="tab"
                :aria-selected="workspaceMainTab === 'ledger'"
                @click="workspaceMainTab = 'ledger'"
              >
                信源主表
              </button>
              <button
                :class="['workspace-tab', { 'is-active': workspaceMainTab === 'intel' }]"
                type="button"
                role="tab"
                :aria-selected="workspaceMainTab === 'intel'"
                @click="workspaceMainTab = 'intel'"
              >
                运行情报坞
              </button>
            </div>
          </section>

          <div v-show="workspaceMainTab === 'ledger'" class="workspace-main-panel workspace-main-ledger">
            <section class="ledger-scope-bar panel">
              <div class="ledger-scope-tabs" role="group" aria-label="主表快捷筛选">
                <button
                  :class="['workspace-tab', { 'is-active': tableScope === 'all' }]"
                  type="button"
                  @click="applyTableScope('all')"
                >
                  全部
                </button>
                <button
                  :class="['workspace-tab', { 'is-active': tableScope === 'enabled' }]"
                  type="button"
                  @click="applyTableScope('enabled')"
                >
                  已启用
                </button>
                <button
                  :class="['workspace-tab', { 'is-active': tableScope === 'disabled' }]"
                  type="button"
                  @click="applyTableScope('disabled')"
                >
                  已停用
                </button>
                <button
                  :class="['workspace-tab', { 'is-active': tableScope === 'warning' }]"
                  type="button"
                  @click="applyTableScope('warning')"
                >
                  告警
                </button>
                <button
                  :class="['workspace-tab', { 'is-active': tableScope === 'failing' }]"
                  type="button"
                  @click="applyTableScope('failing')"
                >
                  失败
                </button>
              </div>
            </section>

            <SourceTable
              :sources="sources"
              :selected-ids="selectedSourceIds"
              :loading="sourceLoading"
              :all-visible-selected="allVisibleSelected"
              :active-source-id="selectedSourceId"
              :has-active-filters="hasActiveFilters"
              :triggering-source-ids="triggeringSourceIds"
              :toggling-source-ids="togglingSourceIds"
              @toggle-all="toggleAllVisible"
              @toggle-select="toggleSelect"
              @inspect-source="inspectSource"
              @toggle-source="toggleSource"
              @trigger-source="triggerSource"
            />

            <footer class="pager-bar panel workspace-pager">
              <div class="pager-copy">
                <strong>第 {{ currentPage }} / {{ totalPages }} 页</strong>
                <span>{{ sourceCatalog?.total_sources || 0 }} 个信源进入目录</span>
              </div>
              <div class="pager-actions">
                <button class="ghost-button" type="button" :disabled="!canPrevPage" @click="goPrevPage">
                  上一页
                </button>
                <button class="ghost-button" type="button" :disabled="!canNextPage" @click="goNextPage">
                  下一页
                </button>
              </div>
            </footer>
          </div>

          <div
            v-show="workspaceMainTab === 'intel'"
            id="section-intel"
            class="workspace-main-panel workspace-main-intel"
          >
            <IntelDock
              :overview="overview"
              :trend="trend"
              :active-tab="intelTab"
              :manual-progress-percent="manualProgressPercent"
              @update:active-tab="intelTab = $event"
            />
          </div>
        </div>

        <aside class="workspace-side-column">
          <section class="panel workspace-summary-card">
            <div class="summary-head">
              <p class="eyebrow">Selection</p>
              <h3>当前筛选概览</h3>
            </div>

            <div class="summary-metrics">
              <div class="summary-item summary-item-primary">
                <span class="meta-label">命中信源</span>
                <strong>{{ sourceCatalog?.filtered_sources || 0 }} 条</strong>
              </div>
              <div class="summary-item summary-item-primary">
                <span class="meta-label">待运行</span>
                <strong>{{ selectedCount }} 个</strong>
              </div>
              <div class="summary-item">
                <span class="meta-label">本页显示</span>
                <strong>{{ sources.length }} 条</strong>
              </div>
              <div class="summary-item">
                <span class="meta-label">自动刷新频率</span>
                <strong>每 {{ refreshCadenceText }}</strong>
              </div>
            </div>

            <div class="summary-actions">
              <button
                class="ghost-button summary-action"
                type="button"
                :disabled="selectAllFilteredLoading || !(sourceCatalog?.filtered_sources || 0)"
                @click="selectAllFiltered"
              >
                {{ selectAllFilteredLabel }}
              </button>
              <button class="ghost-button summary-action" type="button" :disabled="!selectedCount" @click="clearSelection">
                清空已选
              </button>
              <button class="ghost-button summary-action" type="button" @click="openBatchWorkspace">
                去第 3 步：批量执行
              </button>
              <p class="summary-tip">{{ selectionCoverageHint }}</p>
            </div>
          </section>

          <section class="workspace-side-card panel">
            <div class="workspace-side-tabs" role="tablist" aria-label="编排与任务">
              <button
                :class="['workspace-tab', { 'is-active': workspaceSideTab === 'filters' }]"
                type="button"
                role="tab"
                :aria-selected="workspaceSideTab === 'filters'"
                @click="workspaceSideTab = 'filters'"
              >
                筛选
              </button>
              <button
                :class="['workspace-tab', { 'is-active': workspaceSideTab === 'batch' }]"
                type="button"
                role="tab"
                :aria-selected="workspaceSideTab === 'batch'"
                @click="workspaceSideTab = 'batch'"
              >
                批量
              </button>
            </div>

            <section v-show="workspaceSideTab === 'filters'" class="workbench-toolbar workspace-embedded-panel">
              <p class="workspace-panel-intro">先筛选目标信源，再进入第 3 步批量执行。</p>
              <div class="toolbar-row">
                <label class="toolbar-search">
                  <span>搜索</span>
                  <input v-model="filters.keyword" type="text" placeholder="按名称、ID、域名查找" />
                </label>
                <label>
                  <span>维度</span>
                  <select v-model="filters.dimension">
                    <option value="">全部</option>
                    <option
                      v-for="facet in sourceCatalog?.facets?.dimensions || []"
                      :key="facet.key"
                      :value="facet.key"
                    >
                      {{ facet.label || facet.key }}
                    </option>
                  </select>
                </label>
              </div>

              <div class="toolbar-row toolbar-row-bottom">
                <div class="toolbar-summary filter-result-row" role="status" aria-live="polite">
                  <span>{{ filterResultSummary }}</span>
                  <button class="ghost-button" type="button" :disabled="!hasActiveFilters" @click="clearFilters">
                    清空筛选
                  </button>
                </div>
              </div>
            </section>

            <section
              v-show="workspaceSideTab === 'batch'"
              id="section-tasks"
              class="selection-action-bar workspace-embedded-panel"
            >
              <p class="workspace-panel-intro">确认已选信源后，一键启动任务并在此查看结果。</p>
              <div class="action-bar-head">
                <div class="action-bar-copy">
                  <p class="eyebrow">Batch Control</p>
                  <h2>批量任务控制（第 3 步）</h2>
                  <p class="panel-note">主按钮只保留一个，其他动作降级到次操作。</p>
                </div>
                <div class="action-head-metrics">
                  <div class="action-inline-stat">
                    <span>已选信源</span>
                    <strong>{{ selectedCount }}</strong>
                  </div>
                  <div class="action-inline-stat">
                    <span>导出文件</span>
                    <strong>{{ overview?.manual_job.result_file_name || "暂无" }}</strong>
                  </div>
                  <div v-if="overview?.manual_job.is_running" class="action-progress">
                    <strong>{{ manualProgressPercent }}%</strong>
                    <span>{{ overview?.manual_job.current_source || "执行中" }}</span>
                  </div>
                  <span v-else class="panel-note">当前没有运行中的手动任务</span>
                </div>
              </div>

              <div class="action-bar-body">
                <div class="action-config-grid">
                  <label>
                    <span>导出格式</span>
                    <select v-model="manualForm.exportFormat">
                      <option value="json">JSON</option>
                      <option value="csv">CSV</option>
                      <option value="xlsx">Excel (.xlsx)</option>
                      <option value="database">数据库</option>
                    </select>
                  </label>
                  <label>
                    <span>白名单关键词</span>
                    <input v-model="manualForm.keywordFilterText" type="text" placeholder="逗号分隔多个关键词" />
                  </label>
                </div>
                <details class="action-advanced">
                  <summary>高级筛选项</summary>
                  <label>
                    <span>黑名单关键词</span>
                    <input v-model="manualForm.keywordBlacklistText" type="text" placeholder="命中后剔除" />
                  </label>
                </details>

                <div class="action-buttons">
                  <button
                    class="accent-button"
                    type="button"
                    :disabled="!selectedCount || manualActionLoading"
                    @click="startManualJob"
                  >
                    {{ batchPrimaryLabel }}
                  </button>
                  <div class="secondary-actions">
                    <button
                      class="ghost-button"
                      type="button"
                      :disabled="!overview?.manual_job.is_running || manualActionLoading"
                      @click="stopManualJob"
                    >
                      停止任务
                    </button>
                    <a class="ghost-button" :href="consoleApi.getDownloadUrl()" target="_blank" rel="noreferrer">
                      下载最近结果
                    </a>
                  </div>
                </div>
              </div>
            </section>
          </section>
        </aside>
      </section>
    </main>

    <SourceDrawer
      v-if="drawerOpen && activeSource"
      :source="activeSource"
      :logs="sourceLogs"
      :logs-loading="logsLoading"
      :triggering-source-ids="triggeringSourceIds"
      :toggling-source-ids="togglingSourceIds"
      @close="closeDrawer"
      @trigger="triggerSource"
      @toggle="toggleSource"
    />
  </div>
</template>
