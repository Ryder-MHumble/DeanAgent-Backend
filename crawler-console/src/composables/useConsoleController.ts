import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { consoleApi } from "../api/console";
import type {
  ConsoleOverview,
  CrawlLog,
  ManualJobPayload,
  ServerMetrics,
  SourceCatalogResponse,
  SourceItem,
  TrendPoint,
} from "../types";

export function useConsoleController() {
  const overview = ref<ConsoleOverview | null>(null);
  const trend = ref<TrendPoint[]>([]);
  const serverMetrics = ref<ServerMetrics | null>(null);
  const serverMetricsError = ref("");
  const sourceCatalog = ref<SourceCatalogResponse | null>(null);
  const sourceLogs = ref<CrawlLog[]>([]);
  const selectedSourceId = ref("");
  const selectedSourceIds = ref<string[]>([]);
  const sourceLoading = ref(false);
  const logsLoading = ref(false);
  const page = ref(1);
  const isRefreshing = ref(false);
  const manualActionLoading = ref(false);
  const togglingSourceIds = ref<string[]>([]);
  const triggeringSourceIds = ref<string[]>([]);
  const statusMessage = ref("正在连接控制台 API...");
  const errorMessage = ref("");
  const lastAction = ref("");
  const drawerOpen = ref(false);

  const filters = reactive({
    keyword: "",
    dimension: "",
    health_status: "",
    is_enabled: "",
  });

  const manualForm = reactive<{
    keywordFilterText: string;
    keywordBlacklistText: string;
    exportFormat: ManualJobPayload["export_format"];
  }>({
    keywordFilterText: "",
    keywordBlacklistText: "",
    exportFormat: "json",
  });

  let pollTimer: number | null = null;
  let sourceLoadTimer: number | null = null;
  let pollTick = 0;
  let pollInFlight = false;

  const sources = computed(() => sourceCatalog.value?.items || []);
  const selectedCount = computed(() => selectedSourceIds.value.length);
  const allVisibleSelected = computed(() => {
    if (!sources.value.length) {
      return false;
    }
    return sources.value.every((item) => selectedSourceIds.value.includes(item.id));
  });
  const activeSource = computed(() =>
    sources.value.find((item) => item.id === selectedSourceId.value) || null,
  );
  const currentPage = computed(() => sourceCatalog.value?.page || page.value);
  const totalPages = computed(() => Math.max(sourceCatalog.value?.total_pages || 1, 1));
  const canPrevPage = computed(() => currentPage.value > 1);
  const canNextPage = computed(() => currentPage.value < totalPages.value);

  function parseKeywordText(value: string) {
    return value
      .split(/[,\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function clearSourceLoadTimer() {
    if (sourceLoadTimer !== null) {
      window.clearTimeout(sourceLoadTimer);
      sourceLoadTimer = null;
    }
  }

  async function loadOverview() {
    overview.value = await consoleApi.getOverview();
  }

  async function loadTrend() {
    trend.value = await consoleApi.getDailyTrend(7);
  }

  async function loadServerMetrics(allowFailure = false) {
    try {
      serverMetrics.value = await consoleApi.getServerMetrics();
      serverMetricsError.value = "";
    } catch (error) {
      serverMetrics.value = null;
      serverMetricsError.value =
        error instanceof Error ? error.message : "服务器监控加载失败";
      if (!allowFailure) {
        throw error;
      }
    }
  }

  async function fetchLogs(sourceId: string, resetBeforeLoad = false) {
    logsLoading.value = true;
    if (resetBeforeLoad) {
      sourceLogs.value = [];
    }

    try {
      const response = await consoleApi.getSourceLogs(sourceId, 20);
      if (selectedSourceId.value === sourceId) {
        sourceLogs.value = response.logs;
      }
    } finally {
      logsLoading.value = false;
    }
  }

  async function loadSources() {
    sourceLoading.value = true;
    try {
      const nextCatalog = await consoleApi.getSources({
        page: page.value,
        page_size: 50,
        keyword: filters.keyword || null,
        dimension: filters.dimension || null,
        health_status: filters.health_status || null,
        is_enabled: filters.is_enabled === "" ? null : filters.is_enabled,
        include_facets: true,
      });
      sourceCatalog.value = nextCatalog;

      const exists = nextCatalog.items.some((item) => item.id === selectedSourceId.value);
      if (!exists) {
        selectedSourceId.value = "";
        sourceLogs.value = [];
        drawerOpen.value = false;
      }
    } finally {
      sourceLoading.value = false;
    }
  }

  async function refreshAll() {
    if (isRefreshing.value) {
      return;
    }

    isRefreshing.value = true;
    errorMessage.value = "";
    try {
      await Promise.all([loadOverview(), loadTrend(), loadSources(), loadServerMetrics(true)]);
      if (drawerOpen.value && selectedSourceId.value) {
        await fetchLogs(selectedSourceId.value);
      }
      statusMessage.value = "控制台数据已刷新";
      lastAction.value = "";
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "刷新失败";
    } finally {
      isRefreshing.value = false;
    }
  }

  async function inspectSource(sourceId: string) {
    if (!sourceId) {
      return;
    }

    selectedSourceId.value = sourceId;
    drawerOpen.value = true;
    errorMessage.value = "";
    try {
      await fetchLogs(sourceId, true);
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "加载日志失败";
    }
  }

  function closeDrawer() {
    drawerOpen.value = false;
  }

  async function toggleSource(source: SourceItem) {
    if (togglingSourceIds.value.includes(source.id)) {
      return;
    }

    togglingSourceIds.value = [...togglingSourceIds.value, source.id];
    errorMessage.value = "";
    try {
      await consoleApi.updateSource(source.id, !source.is_enabled);
      lastAction.value = `${source.name} 已${source.is_enabled ? "停用" : "启用"}`;
      await Promise.all([loadOverview(), loadSources()]);
      if (drawerOpen.value && selectedSourceId.value === source.id) {
        await fetchLogs(source.id);
      }
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "更新失败";
    } finally {
      togglingSourceIds.value = togglingSourceIds.value.filter((id) => id !== source.id);
    }
  }

  async function triggerSource(sourceId: string) {
    if (triggeringSourceIds.value.includes(sourceId)) {
      return;
    }

    triggeringSourceIds.value = [...triggeringSourceIds.value, sourceId];
    errorMessage.value = "";
    try {
      await consoleApi.triggerSource(sourceId);
      lastAction.value = `${sourceId} 已加入调度执行`;
      await loadOverview();
      if (drawerOpen.value && selectedSourceId.value === sourceId) {
        await fetchLogs(sourceId);
      }
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "触发失败";
    } finally {
      triggeringSourceIds.value = triggeringSourceIds.value.filter((id) => id !== sourceId);
    }
  }

  async function startManualJob() {
    if (!selectedSourceIds.value.length) {
      errorMessage.value = "请先选择至少一个信源";
      return;
    }

    if (manualActionLoading.value) {
      return;
    }

    manualActionLoading.value = true;
    errorMessage.value = "";
    try {
      const payload: ManualJobPayload = {
        source_ids: selectedSourceIds.value,
        keyword_filter: parseKeywordText(manualForm.keywordFilterText),
        keyword_blacklist: parseKeywordText(manualForm.keywordBlacklistText),
        export_format: manualForm.exportFormat,
      };
      await consoleApi.startManualJob(payload);
      lastAction.value = `手动任务已启动，共 ${selectedSourceIds.value.length} 个信源`;
      await loadOverview();
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "启动失败";
    } finally {
      manualActionLoading.value = false;
    }
  }

  async function stopManualJob() {
    if (manualActionLoading.value) {
      return;
    }

    manualActionLoading.value = true;
    errorMessage.value = "";
    try {
      await consoleApi.stopManualJob();
      lastAction.value = "已请求停止当前手动任务";
      await loadOverview();
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "停止失败";
    } finally {
      manualActionLoading.value = false;
    }
  }

  function toggleSelect(sourceId: string) {
    if (selectedSourceIds.value.includes(sourceId)) {
      selectedSourceIds.value = selectedSourceIds.value.filter((item) => item !== sourceId);
      return;
    }
    selectedSourceIds.value = [...selectedSourceIds.value, sourceId];
  }

  function toggleAllVisible() {
    if (allVisibleSelected.value) {
      const visibleSet = new Set(sources.value.map((item) => item.id));
      selectedSourceIds.value = selectedSourceIds.value.filter((item) => !visibleSet.has(item));
      return;
    }

    const merged = new Set([...selectedSourceIds.value, ...sources.value.map((item) => item.id)]);
    selectedSourceIds.value = Array.from(merged);
  }

  function clearFilters() {
    filters.keyword = "";
    filters.dimension = "";
    filters.health_status = "";
    filters.is_enabled = "";
  }

  function goPrevPage() {
    if (!canPrevPage.value) {
      return;
    }
    page.value -= 1;
  }

  function goNextPage() {
    if (!canNextPage.value) {
      return;
    }
    page.value += 1;
  }

  function queueLoadSources() {
    clearSourceLoadTimer();
    sourceLoadTimer = window.setTimeout(async () => {
      try {
        await loadSources();
      } catch (error) {
        errorMessage.value = error instanceof Error ? error.message : "加载信源失败";
      }
    }, 220);
  }

  function startPolling() {
    if (pollTimer !== null) {
      window.clearInterval(pollTimer);
    }

    pollTimer = window.setInterval(async () => {
      if (pollInFlight) {
        return;
      }

      pollInFlight = true;
      pollTick += 1;
      try {
        await Promise.all([loadOverview(), loadServerMetrics(true)]);
        if (pollTick % 3 === 0) {
          await Promise.all([loadTrend(), loadSources()]);
        }
        if (drawerOpen.value && selectedSourceId.value) {
          await fetchLogs(selectedSourceId.value);
        }
      } catch {
        // keep silent during background polling
      } finally {
        pollInFlight = false;
      }
    }, 10000);
  }

  watch(
    () => [filters.keyword, filters.dimension, filters.health_status, filters.is_enabled],
    () => {
      if (page.value !== 1) {
        page.value = 1;
        return;
      }
      queueLoadSources();
    },
  );

  watch(page, () => {
    queueLoadSources();
  });

  onMounted(async () => {
    await refreshAll();
    startPolling();
  });

  onBeforeUnmount(() => {
    if (pollTimer !== null) {
      window.clearInterval(pollTimer);
    }
    clearSourceLoadTimer();
  });

  return {
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
    loadSources,
    logsLoading,
    manualActionLoading,
    manualForm,
    overview,
    page,
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
  };
}
