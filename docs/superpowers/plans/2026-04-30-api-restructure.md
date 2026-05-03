# API Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move route implementation modules out of `app/api/v1` into domain-oriented `app/api` packages while preserving existing `/api/...` HTTP paths.

**Architecture:** `app/api/router.py` becomes the primary aggregate router with `prefix="/api"`. Domain packages (`content`, `operations`, `intel`, `academic`, `social`, `external`, `reports`) own route modules. `app/main.py` imports the new aggregate router, and repository-local direct imports are updated to the new module paths.

**Tech Stack:** Python 3.12, FastAPI `APIRouter`, pytest.

---

### Task 1: Move API modules into domain packages

**Files:**
- Create domain package `__init__.py` files under `app/api/`
- Move route modules from `app/api/v1` and `app/api/v1/intel` into domain packages

- [ ] Create package directories: `content`, `operations`, `intel`, `academic`, `social`, `external`, `reports`.
- [ ] Move modules without changing endpoint bodies.
- [ ] Keep `app/api/v1` empty or remove it after imports are updated.

### Task 2: Rebuild aggregate routers

**Files:**
- Create: `app/api/router.py`
- Modify: `app/api/intel/router.py`
- Modify: `app/main.py`

- [ ] Import route modules from new packages.
- [ ] Register routers with the same prefixes and tags as the old `app/api/v1/router.py`.
- [ ] Keep `institutions` registered last because it has a catch-all route.
- [ ] Update `app/main.py` to import `api_router` from `app.api.router`.

### Task 3: Update direct Python imports

**Files:**
- Modify: tests and scripts that import `app.api.v1` directly.

- [ ] Update `tests/test_api_query_regressions.py` imports.
- [ ] Update `tests/test_publication_api.py` imports.
- [ ] Update `scripts/examples/aminer_detail_api_diagnostic.py` import.
- [ ] Update README/doc code snippets only where they are current executable guidance.

### Task 4: Verify import and selected API tests

**Commands:**
- `python -m compileall app/api tests/test_api_query_regressions.py tests/test_publication_api.py scripts/examples/aminer_detail_api_diagnostic.py`
- `pytest tests/test_api_query_regressions.py tests/test_publication_api.py -q`
