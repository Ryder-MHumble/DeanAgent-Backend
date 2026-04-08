<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { consoleApi } from "./api/console";
import IntelDock from "./components/IntelDock.vue";
import OpsStage from "./components/OpsStage.vue";
import SourceDrawer from "./components/SourceDrawer.vue";
import SourceTable from "./components/SourceTable.vue";
import SystemNav from "./components/SystemNav.vue";
import { useConsoleController } from "./composables/useConsoleController";
import { formatDateTime, formatNumber } from "./utils/consoleFormat";

interface MetricTile {
  label: string;
  value: number | string;
  hint: string;
  tone?: "default" | "warning";
}

const {
  activeSource,
  allVisibleSelected,
  canNextPage,
  canPrevPage,
  clearFilters,
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
  refreshAll,
  serverMetrics,
  serverMetricsError,
  selectedCount,
  selectedSourceId,
  selectedSourceIds,
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

const sectionIds = ["overview", "sources", "tasks", "intel"] as const;
const activeSection = ref<(typeof sectionIds)[number]>("sources");
const intelTab = ref<"manual" | "trend" | "dimensions" | "runs">("runs");
const workspaceMainTab = ref<"ledger" | "intel">("ledger");
const workspaceSideTab = ref<"filters" | "batch">("filters");

let scrollFrame: number | null = null;

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

function navigateToSection(section: (typeof sectionIds)[number]) {
  if (section === "sources") {
    workspaceMainTab.value = "ledger";
  }
  if (section === "tasks") {
    workspaceSideTab.value = "batch";
  }
  if (section === "intel") {
    workspaceMainTab.value = "intel";
  }

  activeSection.value = section;
  document.getElementById(`section-${section}`)?.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
}

function openBatchPanel() {
  workspaceSideTab.value = "batch";
  activeSection.value = "tasks";
}

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

function syncActiveSectionFromScroll() {
  const offset = 220;
  const currentScroll = window.scrollY + offset;

  let nextSection: (typeof sectionIds)[number] = sectionIds[0];
  for (const sectionId of sectionIds) {
    const element = document.getElementById(`section-${sectionId}`);
    if (!element) {
      continue;
    }

    const absoluteTop = element.getBoundingClientRect().top + window.scrollY;
    if (currentScroll >= absoluteTop) {
      nextSection = sectionId;
    }
  }

  activeSection.value = nextSection;
}

function handleWindowScroll() {
  if (scrollFrame !== null) {
    window.cancelAnimationFrame(scrollFrame);
  }

  scrollFrame = window.requestAnimationFrame(() => {
    syncActiveSectionFromScroll();
    scrollFrame = null;
  });
}

onMounted(() => {
  syncActiveSectionFromScroll();
  window.addEventListener("scroll", handleWindowScroll, { passive: true });
  window.addEventListener("resize", handleWindowScroll);
});

onBeforeUnmount(() => {
  if (scrollFrame !== null) {
    window.cancelAnimationFrame(scrollFrame);
  }
  window.removeEventListener("scroll", handleWindowScroll);
  window.removeEventListener("resize", handleWindowScroll);
});
</script>

<template>
  <div class="console-shell">
    <SystemNav
      :active-section="activeSection"
      :scheduler-status="overview?.scheduler_status || null"
      :generated-at="overview?.generated_at || null"
      @navigate="navigateToSection"
    />

    <main class="console-main">
      <header id="section-overview" class="command-header panel">
        <div class="command-copy">
          <p class="eyebrow">Dean Control Tower</p>
          <h1>情报引擎数据控制台</h1>
          <p class="subtitle">以信源主表为中心，把运行趋势、服务器负载、筛选编排和任务动作收进同一块工作台。</p>
        </div>

        <div class="command-actions">
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

      <OpsStage
        :overview="overview"
        :trend="trend"
        :server-metrics="serverMetrics"
        :server-error="serverMetricsError"
      />

      <section class="kpi-band panel">
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

      <section id="section-sources" class="workspace-shell">
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
              <button class="ghost-button summary-action" type="button" @click="openBatchPanel">
                去第 3 步：批量执行
              </button>
              <p class="summary-tip">完成筛选与勾选后，可直接进入批量执行面板。</p>
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
