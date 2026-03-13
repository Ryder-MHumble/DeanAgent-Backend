-- Migration: Add custom_fields JSONB column to support user-defined KV fields
-- Execute in Supabase Dashboard > SQL Editor

ALTER TABLE projects ADD COLUMN IF NOT EXISTS custom_fields jsonb DEFAULT '{}';
ALTER TABLE events ADD COLUMN IF NOT EXISTS custom_fields jsonb DEFAULT '{}';
ALTER TABLE institutions ADD COLUMN IF NOT EXISTS custom_fields jsonb DEFAULT '{}';
ALTER TABLE scholars ADD COLUMN IF NOT EXISTS custom_fields jsonb DEFAULT '{}';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS custom_fields jsonb DEFAULT '{}';

-- Optional: GIN index for querying custom_fields (enable if needed)
-- CREATE INDEX IF NOT EXISTS idx_projects_custom_fields ON projects USING gin (custom_fields);
-- CREATE INDEX IF NOT EXISTS idx_events_custom_fields ON events USING gin (custom_fields);
-- CREATE INDEX IF NOT EXISTS idx_institutions_custom_fields ON institutions USING gin (custom_fields);
-- CREATE INDEX IF NOT EXISTS idx_scholars_custom_fields ON scholars USING gin (custom_fields);
-- CREATE INDEX IF NOT EXISTS idx_articles_custom_fields ON articles USING gin (custom_fields);
