-- Performance indexes for scholar/institution read-write paths.
-- Safe to run multiple times.

CREATE INDEX IF NOT EXISTS idx_scholars_name
  ON scholars (name);

CREATE INDEX IF NOT EXISTS idx_scholars_university
  ON scholars (university);

CREATE INDEX IF NOT EXISTS idx_scholars_department
  ON scholars (department);

CREATE INDEX IF NOT EXISTS idx_scholars_university_department
  ON scholars (university, department);

CREATE INDEX IF NOT EXISTS idx_scholars_university_name
  ON scholars (university, name);

CREATE INDEX IF NOT EXISTS idx_scholars_name_university
  ON scholars (name, university);

CREATE INDEX IF NOT EXISTS idx_scholars_position
  ON scholars (position);

CREATE INDEX IF NOT EXISTS idx_scholars_potential_recruit
  ON scholars (is_potential_recruit);

CREATE INDEX IF NOT EXISTS idx_scholars_advisor_committee
  ON scholars (is_advisor_committee);

CREATE INDEX IF NOT EXISTS idx_scholars_academician
  ON scholars (is_academician);

CREATE INDEX IF NOT EXISTS idx_scholars_email_nonempty
  ON scholars (email)
  WHERE email IS NOT NULL AND email <> '';

CREATE INDEX IF NOT EXISTS idx_scholars_adjunct_status
  ON scholars ((COALESCE(adjunct_supervisor->>'status', '')));

CREATE INDEX IF NOT EXISTS idx_scholars_custom_fields_gin
  ON scholars USING gin (custom_fields);

CREATE INDEX IF NOT EXISTS idx_institutions_parent_id
  ON institutions (parent_id);

CREATE INDEX IF NOT EXISTS idx_institutions_entity_region_type_class
  ON institutions (entity_type, region, org_type, classification);

CREATE INDEX IF NOT EXISTS idx_institutions_name
  ON institutions (name);

ANALYZE scholars;
ANALYZE institutions;
