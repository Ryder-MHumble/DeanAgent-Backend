import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

export const sectionIds = ["overview", "ops", "api", "sources", "tasks", "intel"] as const;
export type SectionId = (typeof sectionIds)[number];

export function useWorkspaceNavigation() {
  const activeSection = ref<SectionId>("sources");
  const workspaceMainTab = ref<"ledger" | "intel">("ledger");
  const workspaceSideTab = ref<"filters" | "batch">("filters");
  const intelTab = ref<"manual" | "trend" | "dimensions" | "runs">("runs");

  let scrollFrame: number | null = null;

  function sectionAnchorId(sectionId: SectionId) {
    if (sectionId === "intel" || sectionId === "sources") {
      return "section-sources";
    }
    return `section-${sectionId}`;
  }

  function readSectionFromUrl(): SectionId | null {
    const params = new URLSearchParams(window.location.search);
    const section = params.get("section");
    if (section && sectionIds.includes(section as SectionId)) {
      return section as SectionId;
    }
    return null;
  }

  function writeSectionToUrl(section: SectionId) {
    const url = new URL(window.location.href);
    url.searchParams.set("section", section);
    const search = url.searchParams.toString();
    window.history.replaceState({}, "", `${url.pathname}${search ? `?${search}` : ""}${url.hash}`);
  }

  function isVisibleSection(sectionId: SectionId) {
    const element = document.getElementById(sectionAnchorId(sectionId));
    if (!element) {
      return false;
    }
    if (element.getClientRects().length === 0) {
      return false;
    }
    return window.getComputedStyle(element).display !== "none";
  }

  function resolveWorkspaceSection(): SectionId {
    if (workspaceMainTab.value === "intel") {
      return "intel";
    }
    if (workspaceSideTab.value === "batch") {
      return "tasks";
    }
    return "sources";
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
    writeSectionToUrl(section);
    await nextTick();
    const target = document.getElementById(sectionAnchorId(section));
    target?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  async function openBatchPanel() {
    workspaceMainTab.value = "ledger";
    workspaceSideTab.value = "batch";
    activeSection.value = "tasks";
    writeSectionToUrl("tasks");
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
    for (const sectionId of ["overview", "ops", "api"] as const) {
      if (!isVisibleSection(sectionId)) {
        continue;
      }
      const element = document.getElementById(sectionAnchorId(sectionId));
      if (!element) {
        continue;
      }

      const absoluteTop = element.getBoundingClientRect().top + window.scrollY;
      if (currentScroll >= absoluteTop) {
        nextSection = sectionId;
      }
    }

    const workspaceRoot = document.getElementById("section-sources");
    if (workspaceRoot) {
      const workspaceTop = workspaceRoot.getBoundingClientRect().top + window.scrollY;
      if (currentScroll >= workspaceTop) {
        nextSection = resolveWorkspaceSection();
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
    const initialSection = readSectionFromUrl();
    if (initialSection === "intel") {
      workspaceMainTab.value = "intel";
      activeSection.value = "intel";
    } else if (initialSection === "tasks") {
      workspaceMainTab.value = "ledger";
      workspaceSideTab.value = "batch";
      activeSection.value = "tasks";
    } else if (initialSection === "sources") {
      workspaceMainTab.value = "ledger";
      activeSection.value = "sources";
    } else if (initialSection) {
      activeSection.value = initialSection;
    }

    syncActiveSectionFromScroll();
    window.addEventListener("scroll", handleWindowScroll, { passive: true });
    window.addEventListener("resize", handleWindowScroll);

    if (initialSection) {
      window.setTimeout(() => {
        const target = document.getElementById(sectionAnchorId(initialSection));
        target?.scrollIntoView({
          behavior: "auto",
          block: "start",
        });
      }, 0);
    }
  });

  onBeforeUnmount(() => {
    if (scrollFrame !== null) {
      window.cancelAnimationFrame(scrollFrame);
    }
    window.removeEventListener("scroll", handleWindowScroll);
    window.removeEventListener("resize", handleWindowScroll);
  });

  watch(
    () => [workspaceMainTab.value, workspaceSideTab.value],
    () => {
      if (activeSection.value === "overview" || activeSection.value === "ops" || activeSection.value === "api") {
        return;
      }
      const nextSection = resolveWorkspaceSection();
      activeSection.value = nextSection;
      writeSectionToUrl(nextSection);
    },
  );

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
