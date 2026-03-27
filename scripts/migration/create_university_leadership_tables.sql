-- Dedicated single table for university leadership monthly full-crawl persistence.
-- Safe to run repeatedly.

CREATE TABLE IF NOT EXISTS university_leadership_current (
  source_id VARCHAR(128) PRIMARY KEY,
  institution_id VARCHAR(128) NULL,
  university_name VARCHAR(256) NOT NULL,
  source_name VARCHAR(256) NULL,
  source_url TEXT NULL,
  dimension VARCHAR(64) NULL,
  group_name VARCHAR(128) NULL,
  crawled_at TIMESTAMPTZ NOT NULL,
  previous_crawled_at TIMESTAMPTZ NULL,
  leader_count INTEGER NOT NULL DEFAULT 0,
  new_leader_count INTEGER NOT NULL DEFAULT 0,
  role_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
  leaders JSONB NOT NULL DEFAULT '[]'::jsonb,
  data_hash VARCHAR(64) NOT NULL,
  change_version INTEGER NOT NULL DEFAULT 1,
  last_changed_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_university_leadership_current_institution_id
  ON university_leadership_current(institution_id);

CREATE INDEX IF NOT EXISTS idx_university_leadership_current_university_name
  ON university_leadership_current(university_name);

CREATE INDEX IF NOT EXISTS idx_university_leadership_current_crawled_at
  ON university_leadership_current(crawled_at DESC);

DROP TABLE IF EXISTS university_leadership_snapshots;
