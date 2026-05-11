# Institution Ranking Tags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured institution ranking tags and query filters for 985/211/双一流/QS bands, then render them in ScholarDB-System.

**Architecture:** Add database columns and a small backend helper for tag normalization and display label generation. Wire fields through Pydantic schemas, response builders, list filters, and FastAPI query parameters. Update ScholarDB-System types and UI to display and filter by the API fields.

**Tech Stack:** FastAPI, Pydantic, PostgreSQL/Supabase SQL migrations, pytest, React, TypeScript, Vite.

---

### Task 1: Backend Tag Helper And Tests

**Files:**
- Create: `app/services/core/institution/ranking_tags.py`
- Test: `tests/test_institution_ranking_tags.py`

- [ ] Write failing tests for QS band derivation, display tag generation, and invalid band normalization.
- [ ] Run `uv run pytest tests/test_institution_ranking_tags.py -v` and verify the tests fail because the helper module does not exist.
- [ ] Implement `derive_qs_rank_band`, `normalize_qs_rank_band`, and `build_institution_tags`.
- [ ] Re-run `uv run pytest tests/test_institution_ranking_tags.py -v` and verify it passes.

### Task 2: Backend API Schema, Builders, And Filters

**Files:**
- Modify: `app/schemas/institution.py`
- Modify: `app/services/core/institution/detail_builder.py`
- Modify: `app/services/core/institution/storage.py`
- Modify: `app/services/core/institution/list_query.py`
- Modify: `app/api/academic/institutions.py`
- Test: `tests/test_institution_ranking_filters.py`

- [ ] Write failing tests showing `get_institutions_unified` filters by `is_985`, `is_211`, `is_double_first_class`, and `qs_rank_band`.
- [ ] Run `uv run pytest tests/test_institution_ranking_filters.py -v` and verify failures before implementation.
- [ ] Add schema fields and query parameters.
- [ ] Add response builder fields and computed `institution_tags`.
- [ ] Add storage fallback columns and normalization before writes.
- [ ] Extend list and hierarchy filtering without removing existing hierarchy count fixes.
- [ ] Run `uv run pytest tests/test_institution_ranking_filters.py tests/test_institution_ranking_tags.py -v`.

### Task 3: Migration And Seed Data

**Files:**
- Create: `scripts/sql/20260511_add_institution_ranking_tags.sql`

- [ ] Add idempotent `ALTER TABLE` statements for the new columns.
- [ ] Add idempotent indexes for quick filters.
- [ ] Seed policy tags for known Chinese universities using official 985/211/双一流 lists.
- [ ] Seed known QS 2026 ranks for institutions commonly present in the current data set, and set unmatched primary universities to `200外`.
- [ ] Sanity-check SQL syntax by inspecting the file and avoiding environment-specific credentials.

### Task 4: ScholarDB-System Types And Detail Rendering

**Files:**
- Modify: `../Scholars-System/src/types/institution.ts`
- Modify: `../Scholars-System/src/components/institution/detail/InstitutionBadges.tsx`
- Modify: `../Scholars-System/src/pages/InstitutionDetailPage.tsx`
- Modify: `../Scholars-System/src/components/institution/InstitutionCard.tsx`

- [ ] Add TypeScript fields for ranking data and tags.
- [ ] Add compact ranking badge rendering.
- [ ] Render tags in the institution detail hero and cards.

### Task 5: ScholarDB-System Quick Filters

**Files:**
- Modify: `../Scholars-System/src/services/institutionApi.ts`
- Modify: `../Scholars-System/src/hooks/useInstitutions.ts`
- Modify: `../Scholars-System/src/pages/InstitutionListPage.tsx`

- [ ] Add filter parameters to the API client and hook type.
- [ ] Add quick filter state for `985`, `211`, `双一流`, and QS bands.
- [ ] Pass filters to flat and hierarchy queries.
- [ ] Reset page behavior remains unchanged because filter changes already reload page 1 via hook dependencies.

### Task 6: Verification

**Files:**
- Backend and frontend touched above.

- [ ] Run focused backend tests: `uv run pytest tests/test_institution_ranking_tags.py tests/test_institution_ranking_filters.py tests/test_institution_org_type_aliases.py tests/test_institution_hierarchy_counts.py -v`.
- [ ] Run frontend build: `npm run build` in `../Scholars-System`.
- [ ] Inspect `git diff --stat` and confirm no unrelated files were modified by this work.
