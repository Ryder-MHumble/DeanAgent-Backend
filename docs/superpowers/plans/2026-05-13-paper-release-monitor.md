# Paper Release Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable monitor script that classifies 2025/2026 paper source status against official publication state and current `papers` table counts, then document the conclusion in the paper warehouse docs.

**Architecture:** Keep the monitoring logic in a single script under `scripts/crawl/`, reuse existing parser helpers for official count extraction, and keep tests focused on verdict classification so the change stays stable and low-risk.

**Tech Stack:** Python, asyncpg pool helpers, httpx, existing crawler parser helpers, pytest

---

### Task 1: Add failing tests for verdict classification

**Files:**
- Create: `tests/test_paper_release_monitor.py`
- Test: `tests/test_paper_release_monitor.py`

- [ ] **Step 1: Write the failing test**

```python
def test_classify_verdict_not_published_yet():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_paper_release_monitor.py -q`
Expected: FAIL because the monitor module does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
def classify_verdict(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_paper_release_monitor.py -q`
Expected: PASS

### Task 2: Implement the monitor script

**Files:**
- Create: `scripts/crawl/monitor_paper_release_status.py`
- Modify: `scripts/README.md`

- [ ] **Step 1: Load paper source configs and DB counts**
- [ ] **Step 2: Implement per-source official status checks**
- [ ] **Step 3: Classify verdicts and render output**
- [ ] **Step 4: Add CLI filters for `--source` and `--year`**

### Task 3: Document the monitoring result

**Files:**
- Modify: `docs/paper_source_crawlers.md`
- Modify: `docs/paper_warehouse.md`

- [ ] **Step 1: Add the monitor script usage**
- [ ] **Step 2: Add 2025 conclusion**
- [ ] **Step 3: Add 2026 per-source conclusion**

### Task 4: Verify

**Files:**
- Test: `tests/test_paper_release_monitor.py`

- [ ] **Step 1: Run unit tests**

Run: `.venv/bin/pytest tests/test_paper_release_monitor.py -q`
Expected: PASS

- [ ] **Step 2: Run the monitor script**

Run: `.venv/bin/python scripts/crawl/monitor_paper_release_status.py`
Expected: rows for 2025/2026 with explicit verdicts

- [ ] **Step 3: Run diff hygiene**

Run: `git diff --check`
Expected: no whitespace or patch format errors
