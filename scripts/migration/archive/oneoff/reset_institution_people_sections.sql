-- One-time cleanup for institution detail page:
-- 1) Clear legacy responsible/governance section data
-- 2) Clear notable_scholars, then use manual scholar-based configuration API

UPDATE institutions
SET
  resident_leaders = '[]'::jsonb,
  degree_committee = '[]'::jsonb,
  teaching_committee = '[]'::jsonb,
  university_leaders = '[]'::jsonb,
  notable_scholars = '[]'::jsonb,
  updated_at = NOW()
WHERE entity_type = 'organization';
