-- Extend source_states with source catalog metadata fields.
-- Safe to run repeatedly.

ALTER TABLE source_states
  ADD COLUMN IF NOT EXISTS source_name VARCHAR(256),
  ADD COLUMN IF NOT EXISTS source_url TEXT,
  ADD COLUMN IF NOT EXISTS dimension VARCHAR(64),
  ADD COLUMN IF NOT EXISTS dimension_name VARCHAR(128),
  ADD COLUMN IF NOT EXISTS group_name VARCHAR(128),
  ADD COLUMN IF NOT EXISTS source_file VARCHAR(128),
  ADD COLUMN IF NOT EXISTS crawl_method VARCHAR(64),
  ADD COLUMN IF NOT EXISTS crawler_class VARCHAR(128),
  ADD COLUMN IF NOT EXISTS schedule VARCHAR(32),
  ADD COLUMN IF NOT EXISTS crawl_interval_minutes INTEGER,
  ADD COLUMN IF NOT EXISTS source_type VARCHAR(64),
  ADD COLUMN IF NOT EXISTS source_platform VARCHAR(64),
  ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}'::text[],
  ADD COLUMN IF NOT EXISTS is_enabled_default BOOLEAN DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS is_supported BOOLEAN DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS institution_name VARCHAR(256),
  ADD COLUMN IF NOT EXISTS institution_tier VARCHAR(32);

UPDATE source_states SET is_supported = TRUE WHERE is_supported IS NULL;
ALTER TABLE source_states ALTER COLUMN is_supported SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_source_states_dimension ON source_states(dimension);
CREATE INDEX IF NOT EXISTS idx_source_states_group_name ON source_states(group_name);
CREATE INDEX IF NOT EXISTS idx_source_states_source_type ON source_states(source_type);
CREATE INDEX IF NOT EXISTS idx_source_states_source_platform ON source_states(source_platform);
CREATE INDEX IF NOT EXISTS idx_source_states_schedule ON source_states(schedule);
CREATE INDEX IF NOT EXISTS idx_source_states_is_supported ON source_states(is_supported);
CREATE INDEX IF NOT EXISTS idx_source_states_institution_tier ON source_states(institution_tier);

CREATE OR REPLACE VIEW source_catalog_overview AS
SELECT
  source_id,
  source_name,
  source_type,
  source_platform,
  dimension,
  dimension_name,
  group_name,
  institution_name,
  institution_tier,
  source_url,
  crawl_method,
  crawler_class,
  schedule,
  crawl_interval_minutes,
  tags,
  source_file,
  is_enabled_default,
  is_enabled_override,
  COALESCE(is_enabled_override, is_enabled_default, TRUE) AS is_enabled_effective,
  is_supported,
  last_crawl_at,
  last_success_at,
  consecutive_failures,
  CASE
    WHEN consecutive_failures >= 3 THEN 'failing'
    WHEN consecutive_failures > 0 THEN 'warning'
    WHEN last_crawl_at IS NOT NULL THEN 'healthy'
    ELSE 'unknown'
  END AS health_status,
  updated_at
FROM source_states
WHERE is_supported = TRUE;

-- 清理 scholars/faculty 目录记录：该类信源不参与定时爬取目录。
DELETE FROM source_states
WHERE lower(COALESCE(dimension, '')) = 'scholars'
   OR lower(COALESCE(crawl_method, '')) = 'faculty';

CREATE OR REPLACE VIEW source_catalog_summary AS
SELECT
  COALESCE(dimension, 'unknown') AS dimension,
  COALESCE(source_type, 'unknown') AS source_type,
  COALESCE(source_platform, 'unknown') AS source_platform,
  COALESCE(crawl_method, 'unknown') AS crawl_method,
  COALESCE(schedule, 'unknown') AS schedule,
  COUNT(*) AS total_sources,
  SUM((COALESCE(is_enabled_override, is_enabled_default, TRUE))::int) AS enabled_sources,
  SUM((last_crawl_at IS NOT NULL)::int) AS crawled_sources,
  SUM((consecutive_failures >= 3)::int) AS failing_sources
FROM source_states
WHERE is_supported = TRUE
GROUP BY
  COALESCE(dimension, 'unknown'),
  COALESCE(source_type, 'unknown'),
  COALESCE(source_platform, 'unknown'),
  COALESCE(crawl_method, 'unknown'),
  COALESCE(schedule, 'unknown');
