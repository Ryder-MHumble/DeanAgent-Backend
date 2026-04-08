<script setup lang="ts">
import type { CrawlLog, SourceItem } from "../types";
import { formatDateTime, healthLabel } from "../utils/consoleFormat";

defineProps<{
  source: SourceItem | null;
  logs: CrawlLog[];
  logsLoading: boolean;
  triggeringSourceIds: string[];
  togglingSourceIds: string[];
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "trigger", sourceId: string): void;
  (event: "toggle", source: SourceItem): void;
}>();
</script>

<template>
  <div class="drawer-layer">
    <button class="drawer-backdrop" type="button" aria-label="关闭详情抽屉" @click="emit('close')" />

    <aside class="source-drawer" aria-label="单源详情抽屉">
      <div v-if="source" class="drawer-shell">
        <header class="drawer-header">
          <div>
            <p class="eyebrow">Source Drawer</p>
            <h2>{{ source.name }}</h2>
            <p class="drawer-subtitle">{{ source.id }}</p>
          </div>
          <div class="drawer-header-actions">
            <span class="status-pill" :data-status="source.health_status">
              {{ healthLabel(source.health_status) }}
            </span>
            <button class="drawer-close" type="button" aria-label="关闭" @click="emit('close')">
              ×
            </button>
          </div>
        </header>

        <div class="drawer-quick-actions">
          <button
            class="ghost-button"
            type="button"
            :disabled="triggeringSourceIds.includes(source.id)"
            @click="emit('trigger', source.id)"
          >
            {{ triggeringSourceIds.includes(source.id) ? "触发中..." : "立即触发" }}
          </button>
          <button
            class="ghost-button"
            type="button"
            :disabled="togglingSourceIds.includes(source.id)"
            @click="emit('toggle', source)"
          >
            {{
              togglingSourceIds.includes(source.id)
                ? "提交中..."
                : source.is_enabled
                  ? "停用信源"
                  : "启用信源"
            }}
          </button>
        </div>

        <section class="drawer-section">
          <div class="drawer-section-header">
            <h3>基础信息</h3>
          </div>
          <div class="drawer-grid">
            <div>
              <span>URL</span>
              <strong>{{ source.url }}</strong>
            </div>
            <div>
              <span>维度</span>
              <strong>{{ source.dimension_name || source.dimension }}</strong>
            </div>
            <div>
              <span>分组</span>
              <strong>{{ source.group || source.source_platform || "未分组" }}</strong>
            </div>
            <div>
              <span>标签</span>
              <strong>{{ source.tags.length ? source.tags.join(" / ") : "未配置" }}</strong>
            </div>
          </div>
        </section>

        <section class="drawer-section">
          <div class="drawer-section-header">
            <h3>运行信息</h3>
          </div>
          <div class="drawer-grid">
            <div>
              <span>调度策略</span>
              <strong>{{ source.schedule }}</strong>
            </div>
            <div>
              <span>抓取方式</span>
              <strong>{{ source.crawl_method }}</strong>
            </div>
            <div>
              <span>最近抓取</span>
              <strong>{{ formatDateTime(source.last_crawl_at) }}</strong>
            </div>
            <div>
              <span>最近成功</span>
              <strong>{{ formatDateTime(source.last_success_at) }}</strong>
            </div>
            <div>
              <span>连续失败</span>
              <strong>{{ source.consecutive_failures }}</strong>
            </div>
            <div v-if="source.crawl_interval_minutes">
              <span>间隔</span>
              <strong>{{ source.crawl_interval_minutes }} 分钟</strong>
            </div>
          </div>
        </section>

        <section class="drawer-section">
          <div class="drawer-section-header">
            <h3>最近日志</h3>
            <span class="drawer-section-note">{{ logsLoading ? "同步中..." : `${logs.length} 条` }}</span>
          </div>

          <div v-if="logsLoading" class="section-empty">日志加载中...</div>
          <div v-else-if="!logs.length" class="section-empty">当前信源暂无日志</div>
          <div v-else class="drawer-log-list">
            <article v-for="log in logs" :key="`${log.source_id}-${log.started_at}`" class="drawer-log">
              <div class="drawer-log-top">
                <span class="status-pill" :data-status="log.status">{{ healthLabel(log.status) }}</span>
                <strong>{{ log.items_new }} / {{ log.items_total }}</strong>
              </div>
              <p>{{ formatDateTime(log.started_at) }}</p>
              <p v-if="log.error_message" class="log-error">{{ log.error_message }}</p>
            </article>
          </div>
        </section>
      </div>
    </aside>
  </div>
</template>
