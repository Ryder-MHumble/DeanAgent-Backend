-- Migration: tag-based event/project model + scholar linkage fields
-- Date: 2026-03-26
--
-- Goal:
-- 1) Event: keep classification tags + summary/time/location/scholars + cover photo
-- 2) Project: convert to classification-tag records with scholar_ids
-- 3) Scholar: persist participated_event_ids / project_tags / is_cobuild_scholar

BEGIN;

-- ---------------------------------------------------------------------------
-- events: ensure columns required by the simplified event model exist
-- ---------------------------------------------------------------------------
ALTER TABLE public.events ADD COLUMN IF NOT EXISTS event_time VARCHAR(64);
ALTER TABLE public.events ADD COLUMN IF NOT EXISTS poster_url TEXT;

-- ---------------------------------------------------------------------------
-- projects: add tag-oriented columns while keeping legacy fields for compatibility
-- ---------------------------------------------------------------------------
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS subcategory TEXT;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS scholar_ids TEXT[];

-- Optional but recommended: allow simplified payloads without legacy mandatory fields.
ALTER TABLE public.projects ALTER COLUMN name DROP NOT NULL;
ALTER TABLE public.projects ALTER COLUMN status DROP NOT NULL;
ALTER TABLE public.projects ALTER COLUMN pi_name DROP NOT NULL;
ALTER TABLE public.projects ALTER COLUMN status SET DEFAULT '在研';
ALTER TABLE public.projects ALTER COLUMN pi_name SET DEFAULT '系统标签';

-- Backfill title/summary from legacy columns.
UPDATE public.projects
SET title = COALESCE(NULLIF(title, ''), name)
WHERE COALESCE(title, '') = '';

UPDATE public.projects
SET summary = COALESCE(summary, description, '')
WHERE summary IS NULL;

-- Backfill subcategory from custom_fields when available.
UPDATE public.projects
SET subcategory = COALESCE(NULLIF(subcategory, ''), NULLIF(custom_fields ->> 'subcategory', ''))
WHERE COALESCE(subcategory, '') = '';

-- Backfill scholar_ids from related_scholars JSON.
UPDATE public.projects
SET scholar_ids = COALESCE(
    scholar_ids,
    (
        SELECT ARRAY_AGG(DISTINCT sid)
        FROM (
            SELECT NULLIF(TRIM(COALESCE(item ->> 'scholar_id', item ->> 'id', item ->> 'url_hash', '')), '') AS sid
            FROM jsonb_array_elements(COALESCE(related_scholars, '[]'::jsonb)) item
        ) t
        WHERE sid IS NOT NULL
    ),
    ARRAY[]::text[]
)
WHERE scholar_ids IS NULL;

-- ---------------------------------------------------------------------------
-- scholars: add dedicated event/project linkage columns
-- ---------------------------------------------------------------------------
ALTER TABLE public.scholars ADD COLUMN IF NOT EXISTS participated_event_ids TEXT[] DEFAULT ARRAY[]::text[];
ALTER TABLE public.scholars ADD COLUMN IF NOT EXISTS project_tags JSONB DEFAULT '[]'::jsonb;
ALTER TABLE public.scholars ADD COLUMN IF NOT EXISTS is_cobuild_scholar BOOLEAN DEFAULT FALSE;

-- Backfill participated_event_ids from events.scholar_ids.
WITH event_map AS (
    SELECT
        s.id AS scholar_id,
        COALESCE(
            ARRAY_AGG(e.id ORDER BY e.event_date DESC) FILTER (WHERE e.id IS NOT NULL),
            ARRAY[]::text[]
        ) AS event_ids
    FROM public.scholars s
    LEFT JOIN public.events e
        ON s.id = ANY(COALESCE(e.scholar_ids, ARRAY[]::text[]))
    GROUP BY s.id
)
UPDATE public.scholars s
SET participated_event_ids = event_map.event_ids
FROM event_map
WHERE s.id = event_map.scholar_id;

-- Seed project_tags from legacy single-value fields when still empty.
UPDATE public.scholars
SET project_tags = CASE
    WHEN COALESCE(project_category, '') <> '' OR COALESCE(project_subcategory, '') <> '' THEN
        jsonb_build_array(
            jsonb_build_object(
                'category', COALESCE(project_category, ''),
                'subcategory', COALESCE(project_subcategory, ''),
                'project_id', '',
                'project_title', ''
            )
        )
    ELSE '[]'::jsonb
END
WHERE project_tags IS NULL OR project_tags = '[]'::jsonb;

-- Merge in tags inferred from projects.scholar_ids.
WITH project_links AS (
    SELECT
        sid.scholar_id,
        jsonb_agg(
            DISTINCT jsonb_build_object(
                'category', COALESCE(p.category, ''),
                'subcategory', COALESCE(p.subcategory, ''),
                'project_id', p.id,
                'project_title', COALESCE(p.title, p.name, '')
            )
        ) AS tags
    FROM public.projects p
    CROSS JOIN LATERAL unnest(COALESCE(p.scholar_ids, ARRAY[]::text[])) sid(scholar_id)
    GROUP BY sid.scholar_id
)
UPDATE public.scholars s
SET project_tags = CASE
    WHEN project_links.tags IS NULL THEN s.project_tags
    WHEN s.project_tags IS NULL OR s.project_tags = '[]'::jsonb THEN project_links.tags
    ELSE s.project_tags || project_links.tags
END
FROM project_links
WHERE s.id = project_links.scholar_id;

-- Normalize legacy single-value columns from first project tag.
UPDATE public.scholars
SET
    project_category = COALESCE(project_tags -> 0 ->> 'category', ''),
    project_subcategory = COALESCE(project_tags -> 0 ->> 'subcategory', '');

-- Derive cobuild flag.
UPDATE public.scholars
SET is_cobuild_scholar = jsonb_array_length(COALESCE(project_tags, '[]'::jsonb)) > 0;

COMMIT;
