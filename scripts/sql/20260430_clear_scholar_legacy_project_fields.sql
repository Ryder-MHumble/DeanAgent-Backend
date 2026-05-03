-- Clear legacy scholar project mirror fields and remove the obsolete import marker.
--
-- Project membership should be represented by real project relations or
-- metadata-derived tags, not by scholars.project_category/project_subcategory.
-- Identity/student/mainland flags live under custom_fields.

BEGIN;

UPDATE scholars
SET
  project_category = '',
  project_subcategory = '',
  custom_fields = CASE
    WHEN custom_fields ? 'mainland_student_import' THEN
      jsonb_set(
        jsonb_set(
          custom_fields - 'mainland_student_import',
          '{profile_flags}',
          COALESCE((custom_fields - 'mainland_student_import')->'profile_flags', '{}'::jsonb)
            || '{"is_mainland": true}'::jsonb,
          true
        ),
        '{metadata_profile}',
        COALESCE((custom_fields - 'mainland_student_import')->'metadata_profile', '{}'::jsonb)
          || '{"is_mainland": true}'::jsonb,
        true
      )
    ELSE custom_fields
  END,
  updated_at = NOW()
WHERE
  COALESCE(project_category, '') <> ''
  OR COALESCE(project_subcategory, '') <> ''
  OR custom_fields ? 'mainland_student_import';

COMMIT;
