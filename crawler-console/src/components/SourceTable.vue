<script setup lang="ts">
import type { SourceItem } from "../types";
import { formatDateTime, healthLabel } from "../utils/consoleFormat";

const props = defineProps<{
  sources: SourceItem[];
  selectedIds: string[];
  loading: boolean;
  allVisibleSelected: boolean;
  activeSourceId: string;
  hasActiveFilters: boolean;
  triggeringSourceIds: string[];
  togglingSourceIds: string[];
}>();

const emit = defineEmits<{
  (event: "toggle-select", sourceId: string): void;
  (event: "toggle-all"): void;
  (event: "inspect-source", sourceId: string): void;
  (event: "trigger-source", sourceId: string): void;
  (event: "toggle-source", source: SourceItem): void;
}>();

function isSelected(sourceId: string) {
  return props.selectedIds.includes(sourceId);
}

function isTriggering(sourceId: string) {
  return props.triggeringSourceIds.includes(sourceId);
}

function isToggling(sourceId: string) {
  return props.togglingSourceIds.includes(sourceId);
}

function inspect(sourceId: string) {
  emit("inspect-source", sourceId);
}

function onRowKeydown(event: KeyboardEvent, sourceId: string) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    inspect(sourceId);
  }
}
</script>

<template>
  <section class="source-ledger panel">
    <div class="panel-header compact">
      <div>
        <p class="eyebrow">Source Ledger</p>
        <h2>信源主表</h2>
      </div>
    </div>

    <div v-if="loading" class="table-empty" role="status" aria-live="polite">正在刷新信源工作表...</div>
    <div v-else-if="!sources.length" class="table-empty" role="status" aria-live="polite">
      {{ hasActiveFilters ? "没有匹配当前筛选条件的信源" : "暂无信源数据" }}
    </div>

    <template v-else>
      <div class="table-shell desktop-table">
        <table class="source-table">
          <caption
            style="
              position: absolute;
              width: 1px;
              height: 1px;
              padding: 0;
              margin: -1px;
              overflow: hidden;
              clip: rect(0, 0, 0, 0);
              white-space: nowrap;
              border: 0;
            "
          >
            信源主表，可选择信源并使用运行、启停操作。点击任意数据行可查看详情。
          </caption>
          <thead>
            <tr>
              <th class="checkbox-cell">
                <input
                  :checked="allVisibleSelected"
                  type="checkbox"
                  aria-label="本页全选"
                  @change="emit('toggle-all')"
                />
              </th>
              <th>信源</th>
              <th>状态</th>
              <th>调度</th>
              <th>最近运行</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="source in sources"
              :key="source.id"
              :class="[
                'source-row',
                { 'is-active': source.id === activeSourceId, 'is-selected': isSelected(source.id) },
              ]"
              tabindex="0"
              role="button"
              :aria-label="`查看 ${source.name} 详情`"
              @click="inspect(source.id)"
              @keydown="onRowKeydown($event, source.id)"
            >
              <td class="checkbox-cell" @click.stop>
                <input
                  :checked="isSelected(source.id)"
                  type="checkbox"
                  :aria-label="`选择 ${source.name}`"
                  @change="emit('toggle-select', source.id)"
                />
              </td>
              <th scope="row">
                <span class="source-name">{{ source.name }}</span>
              </th>
              <td>
                <span class="status-pill" :data-status="source.health_status">
                  {{ healthLabel(source.health_status) }}
                </span>
                <div class="source-meta">{{ source.is_enabled ? "已启用" : "已停用" }}</div>
                <div v-if="source.consecutive_failures > 0" class="source-meta">
                  连续失败 {{ source.consecutive_failures }}
                </div>
              </td>
              <td>
                <div>{{ source.schedule }}</div>
                <div class="source-meta">{{ source.crawl_method }}</div>
                <div v-if="source.crawl_interval_minutes" class="source-meta">
                  间隔 {{ source.crawl_interval_minutes }} 分钟
                </div>
              </td>
              <td>
                <div>{{ formatDateTime(source.last_crawl_at) }}</div>
                <div class="source-meta">成功 {{ formatDateTime(source.last_success_at) }}</div>
              </td>
              <td @click.stop>
                <div class="row-actions">
                  <button
                    class="ghost-button"
                    type="button"
                    :disabled="isTriggering(source.id)"
                    :aria-label="`触发 ${source.name}`"
                    @click="emit('trigger-source', source.id)"
                  >
                    {{ isTriggering(source.id) ? "执行中..." : "运行" }}
                  </button>
                  <button
                    class="ghost-button"
                    type="button"
                    :disabled="isToggling(source.id)"
                    :aria-label="`${source.is_enabled ? '停用' : '启用'} ${source.name}`"
                    @click="emit('toggle-source', source)"
                  >
                    {{ isToggling(source.id) ? "提交中..." : source.is_enabled ? "停用" : "启用" }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="source-cards">
        <article
          v-for="source in sources"
          :key="`card-${source.id}`"
          :class="[
            'source-card',
            { 'is-active': source.id === activeSourceId, 'is-selected': isSelected(source.id) },
          ]"
          tabindex="0"
          role="button"
          :aria-label="`查看 ${source.name} 详情`"
          @click="inspect(source.id)"
          @keydown="onRowKeydown($event, source.id)"
        >
          <div class="source-card-top">
            <label class="card-check" @click.stop>
              <input
                :checked="isSelected(source.id)"
                type="checkbox"
                :aria-label="`选择 ${source.name}`"
                @change="emit('toggle-select', source.id)"
              />
              <span>选中</span>
            </label>
            <span class="status-pill" :data-status="source.health_status">
              {{ healthLabel(source.health_status) }}
            </span>
          </div>

          <strong class="source-name card-name-link">
            {{ source.name }}
          </strong>

          <div class="source-card-grid">
            <div>
              <span>归属</span>
              <strong>{{ source.dimension_name || source.dimension }}</strong>
            </div>
            <div>
              <span>调度</span>
              <strong>{{ source.schedule }}</strong>
            </div>
            <div>
              <span>抓取</span>
              <strong>{{ source.crawl_method }}</strong>
            </div>
            <div>
              <span>最近成功</span>
              <strong>{{ formatDateTime(source.last_success_at) }}</strong>
            </div>
          </div>

          <div class="row-actions">
            <button
              class="ghost-button"
              type="button"
              :disabled="isTriggering(source.id)"
              :aria-label="`触发 ${source.name}`"
              @click.stop="emit('trigger-source', source.id)"
            >
              {{ isTriggering(source.id) ? "执行中..." : "运行" }}
            </button>
            <button
              class="ghost-button"
              type="button"
              :disabled="isToggling(source.id)"
              :aria-label="`${source.is_enabled ? '停用' : '启用'} ${source.name}`"
              @click.stop="emit('toggle-source', source)"
            >
              {{
                isToggling(source.id)
                  ? "提交中..."
                  : source.is_enabled
                    ? "停用"
                    : "启用"
              }}
            </button>
          </div>
        </article>
      </div>
    </template>
  </section>
</template>
