<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

export interface DarkSelectOption {
  label: string;
  value: string | number;
}

const props = withDefaults(
  defineProps<{
    modelValue: string | number;
    options: DarkSelectOption[];
    placeholder?: string;
    disabled?: boolean;
  }>(),
  {
    placeholder: "请选择",
    disabled: false,
  },
);

const emit = defineEmits<{
  (event: "update:modelValue", value: string | number): void;
}>();

const rootRef = ref<HTMLElement | null>(null);
const isOpen = ref(false);

const selectedOption = computed(() =>
  props.options.find((option) => option.value === props.modelValue) || null,
);

function close() {
  isOpen.value = false;
}

function toggle() {
  if (props.disabled) {
    return;
  }
  isOpen.value = !isOpen.value;
}

function selectOption(option: DarkSelectOption) {
  emit("update:modelValue", option.value);
  close();
}

function handleDocumentPointerDown(event: Event) {
  const target = event.target;
  if (!(target instanceof Node)) {
    return;
  }
  if (!rootRef.value?.contains(target)) {
    close();
  }
}

function handleEscape(event: KeyboardEvent) {
  if (event.key === "Escape") {
    close();
  }
}

onMounted(() => {
  document.addEventListener("pointerdown", handleDocumentPointerDown);
  document.addEventListener("keydown", handleEscape);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", handleDocumentPointerDown);
  document.removeEventListener("keydown", handleEscape);
});
</script>

<template>
  <div ref="rootRef" class="dark-select" :data-open="isOpen" :data-disabled="disabled">
    <button
      class="dark-select-trigger"
      type="button"
      :disabled="disabled"
      aria-haspopup="listbox"
      :aria-expanded="isOpen"
      @click="toggle"
    >
      <span class="dark-select-label">{{ selectedOption?.label || placeholder }}</span>
      <span class="dark-select-caret" aria-hidden="true"></span>
    </button>

    <div v-if="isOpen" class="dark-select-menu" role="listbox">
      <button
        v-for="option in options"
        :key="String(option.value)"
        :class="['dark-select-option', { 'is-active': option.value === modelValue }]"
        type="button"
        role="option"
        :aria-selected="option.value === modelValue"
        @click="selectOption(option)"
      >
        <span>{{ option.label }}</span>
        <span v-if="option.value === modelValue" class="dark-select-check" aria-hidden="true">•</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.dark-select {
  position: relative;
  min-width: 0;
}

.dark-select-trigger {
  display: flex;
  width: 100%;
  min-height: 42px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(126, 148, 171, 0.2);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.025)),
    rgba(8, 15, 25, 0.92);
  color: var(--text);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 140ms ease,
    background 140ms ease,
    transform 140ms ease;
}

.dark-select[data-open="true"] .dark-select-trigger {
  border-color: rgba(105, 212, 255, 0.48);
  background:
    linear-gradient(180deg, rgba(105, 212, 255, 0.13), rgba(255, 255, 255, 0.03)),
    rgba(8, 15, 25, 0.96);
}

.dark-select-trigger:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.dark-select-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dark-select-caret {
  width: 10px;
  height: 10px;
  flex: 0 0 auto;
  border-right: 1.5px solid currentColor;
  border-bottom: 1.5px solid currentColor;
  transform: rotate(45deg) translateY(-1px);
  opacity: 0.8;
}

.dark-select-menu {
  position: absolute;
  z-index: 30;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  display: grid;
  gap: 4px;
  max-height: 260px;
  overflow: auto;
  padding: 8px;
  border-radius: 14px;
  border: 1px solid rgba(126, 148, 171, 0.24);
  background:
    linear-gradient(180deg, rgba(17, 27, 41, 0.98), rgba(6, 12, 21, 0.98));
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.32);
}

.dark-select-option {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
}

.dark-select-option:hover,
.dark-select-option.is-active {
  background: rgba(105, 212, 255, 0.12);
}

.dark-select-option.is-active {
  color: #dff8ff;
}

.dark-select-check {
  color: var(--cyan);
  font-size: 18px;
  line-height: 1;
}
</style>
