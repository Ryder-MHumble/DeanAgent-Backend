<script setup lang="ts">
import { formatDateTime } from "../utils/consoleFormat";

const props = defineProps<{
  activeSection: string;
  schedulerStatus: "running" | "not_started" | null;
  generatedAt: string | null;
}>();

const navGroups = [
  {
    id: "monitor",
    title: "监控",
    items: [
      { id: "overview", label: "总览", meta: "Overview" },
      { id: "ops", label: "运行", meta: "Ops" },
      { id: "api", label: "API", meta: "OpenRouter" },
    ],
  },
  {
    id: "execution",
    title: "执行",
    items: [
      { id: "sources", label: "信源", meta: "Catalog" },
      { id: "tasks", label: "批量", meta: "Batch" },
      { id: "intel", label: "情报", meta: "Intel" },
    ],
  },
] as const;

const emit = defineEmits<{
  (event: "navigate", section: "overview" | "ops" | "api" | "sources" | "tasks" | "intel"): void;
}>();
</script>

<template>
  <aside class="system-nav">
    <div class="nav-brand">
      <span class="brand-mark" aria-hidden="true">
        <span class="brand-orbit brand-orbit-outer"></span>
        <span class="brand-orbit brand-orbit-inner"></span>
        <span class="brand-glow"></span>
        <span class="brand-core">DC</span>
      </span>
      <div class="brand-copy">
        <strong>Dean Control</strong>
        <span>Crawler Ops Center</span>
      </div>
    </div>

    <nav class="nav-list" aria-label="控制台分区导航">
      <section v-for="group in navGroups" :key="group.id" class="nav-group">
        <p class="nav-group-title">{{ group.title }}</p>
        <button
          v-for="section in group.items"
          :key="section.id"
          :class="['nav-item', { 'is-active': activeSection === section.id }]"
          type="button"
          @click="emit('navigate', section.id)"
        >
          <span class="nav-item-icon" :data-kind="section.id" aria-hidden="true">
            <span class="nav-item-glyph"></span>
          </span>
          <span class="nav-item-copy">
            <span class="nav-item-label">{{ section.label }}</span>
            <span class="nav-item-meta">{{ section.meta }}</span>
          </span>
        </button>
      </section>
    </nav>

    <div class="nav-status">
      <span class="nav-status-label">调度器</span>
      <strong>{{ schedulerStatus === "running" ? "运行中" : "未启动" }}</strong>
      <span class="nav-status-time">{{ formatDateTime(generatedAt) }}</span>
    </div>
  </aside>
</template>
