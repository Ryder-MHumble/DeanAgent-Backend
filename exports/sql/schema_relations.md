# Database Relations

## Foreign Keys

- `event_scholars.event_id` -> `events.id`
- `event_scholars.scholar_id` -> `scholars.id`
- `event_taxonomy.parent_id` -> `event_taxonomy.id`
- `institutions.parent_id` -> `institutions.id`
- `scholar_awards.scholar_id` -> `scholars.id`
- `scholar_dynamic_updates.scholar_id` -> `scholars.id`
- `scholar_education.scholar_id` -> `scholars.id`
- `scholar_patents.scholar_id` -> `scholars.id`
- `scholar_publications.scholar_id` -> `scholars.id`
- `supervised_students.scholar_id` -> `scholars.id`

## Read-only Views

- `intel_cache_latest`
- `scholars_with_institution`
