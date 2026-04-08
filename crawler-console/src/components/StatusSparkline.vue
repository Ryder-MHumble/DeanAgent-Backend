<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  values: number[];
}>();

const points = computed(() => {
  if (!props.values.length) {
    return "";
  }

  const width = 320;
  const height = 96;
  const max = Math.max(...props.values, 1);
  const step = props.values.length > 1 ? width / (props.values.length - 1) : width;

  return props.values
    .map((value, index) => {
      const x = index * step;
      const y = height - (value / max) * height;
      return `${x},${y}`;
    })
    .join(" ");
});
</script>

<template>
  <svg viewBox="0 0 320 96" preserveAspectRatio="none" class="sparkline">
    <defs>
      <linearGradient id="sparkline-fill" x1="0%" x2="0%" y1="0%" y2="100%">
        <stop offset="0%" stop-color="rgba(247, 181, 56, 0.45)" />
        <stop offset="100%" stop-color="rgba(247, 181, 56, 0)" />
      </linearGradient>
    </defs>
    <polyline v-if="points" :points="points" fill="none" stroke="var(--accent)" stroke-width="3" />
    <polygon
      v-if="points"
      :points="`0,96 ${points} 320,96`"
      fill="url(#sparkline-fill)"
    />
  </svg>
</template>
