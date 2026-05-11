# Institution Ranking Tags Design

## Goal

Add maintainable ranking and policy tags to primary university institutions so ScholarDB-System can display and filter institutions by `985`, `211`, `双一流`, and QS rank bands.

## Scope

- Applies to `institutions` rows where `entity_type = 'organization'` and `org_type = '高校'`.
- Adds structured columns rather than storing tags only in `custom_fields`.
- Exposes both raw fields and a computed `institution_tags` list from the institutions API.
- Adds list-query filters for the new fields.
- Renders tags on ScholarDB-System institution detail and institution cards, with a compact filter control on the institution list page.

## Data Model

New `institutions` columns:

- `is_985 boolean not null default false`
- `is_211 boolean not null default false`
- `is_double_first_class boolean not null default false`
- `qs_rank integer null`
- `qs_rank_band varchar null`

Allowed QS bands:

- `前30`
- `前50`
- `前100`
- `前200`
- `200外`

`qs_rank_band` is derived from `qs_rank` when a specific rank is available. If a primary university has no known top-200 rank, migration data may set `qs_rank_band = '200外'`.

## API Contract

`GET /api/institutions` accepts new optional filters:

- `is_985`
- `is_211`
- `is_double_first_class`
- `qs_rank_band`

Institution list/detail/hierarchy responses include:

- `is_985`
- `is_211`
- `is_double_first_class`
- `qs_rank`
- `qs_rank_band`
- `institution_tags`

`institution_tags` display order:

1. `985`
2. `211`
3. `双一流`
4. `QS <band>`

## Frontend

ScholarDB-System renders `institution_tags` in the institution detail hero label area and on institution cards. The institution list page adds quick filters for `985`, `211`, `双一流`, and QS bands.

## Verification

- Backend unit tests cover tag computation and list filtering.
- Frontend TypeScript build verifies the new response fields and UI wiring.
