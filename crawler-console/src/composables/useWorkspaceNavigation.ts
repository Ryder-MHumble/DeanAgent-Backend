import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";

export const sectionIds = ["overview", "ops", "api", "sources", "tasks", "intel"] as const;
export type SectionId = (typeof sectionIds)[number];

export function useWorkspaceNavigation() {
  const activeSection = ref<SectionId>("sources");
  const workspaceMainTab = ref<"ledger" | "intel">("ledger");
  const workspaceSideTab = ref<"filters" | "batch">("filters");
  const intelTab = ref<"manual" | "trend" | "dimensions" | "runs">("runs");

  let scrollFrame: number | null = null;

  function isVisibleSection(sectionId: SectionId) {
    const element = document.getElementById(`section-${sectionId}`);
    if (!element) {
      return false;
    }
    if (element.getClientRects().length === 0) {
      return false;
    }
    return window.getComputedStyle(element).display !== "none";
  }

  async function navigateToSection(section: SectionId) {
    if (section === "sources" || section === "tasks") {
      workspaceMainTab.value = "ledger";
    }
    if (section === "tasks") {
      workspaceSideTab.value = "batch";
    }
    if (section === "intel") {
      workspaceMainTab.value = "intel";
    }
    if (section === "ops" || section === "overview" || section === "api") {
      workspaceMainTab.value = "ledger";
    }

    activeSection.value = section;
    await nextTick();
    const target = document.getElementById(`section-${section}`);
    target?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  async function openBatchPanel() {
    workspaceMainTab.value = "ledger";
    workspaceSideTab.value = "batch";
    activeSection.value = "tasks";
    await nextTick();
    const target = document.getElementById("section-tasks");
    target?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  function syncActiveSectionFromScroll() {
    const offset = 220;
    const currentScroll = window.scrollY + offset;

    let nextSection: SectionId = sectionIds[0];
    for (const sectionId of sectionIds) {
      if (!isVisibleSection(sectionId)) {
        continue;
      }
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

  return {
    activeSection,
    intelTab,
    navigateToSection,
    openBatchPanel,
    sectionIds,
    workspaceMainTab,
    workspaceSideTab,
  };
}
