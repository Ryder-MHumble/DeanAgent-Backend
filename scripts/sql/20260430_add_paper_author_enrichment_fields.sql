-- Papers table: add author-level enrichment fields sourced from the
-- academic-monitor /api/v1/identity/enrich-paper service.
--
-- All three new columns are JSONB arrays indexed by author_order (1-based).
-- They parallel the existing `authors` and `affiliations` arrays, so callers
-- should either:
--   * emit a row per author with consistent `author_order`, or
--   * emit a parallel array whose length equals `jsonb_array_length(authors)`.
--
-- Conventions (documented alongside the schema because they are domain rules):
--
-- author_descriptions  : [{ "author_order": 1, "author_name": "...",
--                           "description": "现任 X 的 Postdoc（2026-2029）；..." }]
--
-- author_experiences   : [{ "author_order": 1, "author_name": "...",
--                           "experiences": [
--                               { "position": "Postdoc", "start": 2026, "end": 2029,
--                                 "institution": "Xidian University",
--                                 "department": "CS", "domain": "xidian.edu.cn",
--                                 "country": "CN" },
--                               ...
--                           ] }]
--
-- profile_flags        : [{ "author_order": 1, "author_name": "...",
--                           "profile_id": "~First_Last1",
--                           "profile_url": "https://openreview.net/profile?id=...",
--                           "is_chinese": true, "is_current_student": false,
--                           "evidence": {...}, "resolution": {...} }]
--
-- These three columns are the authoritative source for incrementally
-- backfilling `scholars.custom_fields` downstream.

ALTER TABLE papers
    ADD COLUMN IF NOT EXISTS author_descriptions JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS author_experiences  JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS profile_flags       JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN papers.author_descriptions IS
    'Per-author profile summary from OpenReview history, indexed by author_order. Populated by academic-monitor /api/v1/identity/enrich-paper.';
COMMENT ON COLUMN papers.author_experiences IS
    'Per-author structured Career & Education history from OpenReview, indexed by author_order. Populated by academic-monitor /api/v1/identity/enrich-paper.';
COMMENT ON COLUMN papers.profile_flags IS
    'Per-author identity flags (is_chinese, is_current_student) + evidence, indexed by author_order. Populated by academic-monitor /api/v1/identity/enrich-paper.';

-- Partial index to quickly find papers still needing enrichment.
CREATE INDEX IF NOT EXISTS idx_papers_pending_enrichment
    ON papers(updated_at)
    WHERE author_descriptions = '[]'::jsonb OR profile_flags = '[]'::jsonb;
