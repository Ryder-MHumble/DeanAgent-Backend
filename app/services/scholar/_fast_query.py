"""Fast SQL-backed query helpers for scholar list/detail endpoints."""
from __future__ import annotations

import math
from typing import Any

from app.db.pool import get_pool
from app.services.core.institution.classification import normalize_org_type
from app.services.scholar._data import _merge_annotation
from app.services.scholar._filters import (
    _get_org_type,
    _get_region,
    get_institution_classification_map,
)
from app.services.scholar._achievement_tags import parse_achievement_filter_tokens
from app.services.scholar._transformers import _to_list_item
from app.services.stores import scholar_annotation_store as annotation_store

_SCHOLAR_COLUMNS_CACHE: set[str] | None = None

_BASE_LIST_SELECT_FIELDS: tuple[str, ...] = (
    "id AS url_hash",
    "name",
    "name_en",
    "photo_url",
    "university",
    "department",
    "position",
    "academic_titles",
    "is_academician",
    "research_areas",
    "email",
    "profile_url",
)

_OPTIONAL_LIST_SELECT_FIELDS: dict[str, str] = {
    "lab_url": "''::text AS lab_url",
    "google_scholar_url": "''::text AS google_scholar_url",
    "dblp_url": "''::text AS dblp_url",
    "orcid": "''::text AS orcid",
    "is_potential_recruit": "FALSE AS is_potential_recruit",
    "is_advisor_committee": "FALSE AS is_advisor_committee",
    "adjunct_supervisor": "'{}'::jsonb AS adjunct_supervisor",
    "project_category": "''::text AS project_category",
    "project_subcategory": "''::text AS project_subcategory",
}


def _normalize_exact_text(value: str) -> str:
    return " ".join((value or "").strip().split()).lower()


async def _get_scholar_columns() -> set[str]:
    global _SCHOLAR_COLUMNS_CACHE
    if _SCHOLAR_COLUMNS_CACHE is not None:
        return _SCHOLAR_COLUMNS_CACHE

    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='scholars'
        """,
    )
    _SCHOLAR_COLUMNS_CACHE = {str(r["column_name"]) for r in rows}
    return _SCHOLAR_COLUMNS_CACHE


async def _build_list_select_sql() -> str:
    scholar_cols = await _get_scholar_columns()
    fields = list(_BASE_LIST_SELECT_FIELDS)
    for column, fallback_sql in _OPTIONAL_LIST_SELECT_FIELDS.items():
        fields.append(column if column in scholar_cols else fallback_sql)
    if "project_tags" in scholar_cols:
        fields.append("project_tags")
    else:
        fields.append("'[]'::jsonb AS project_tags")
    if "participated_event_ids" in scholar_cols:
        fields.append("participated_event_ids")
    else:
        fields.append("ARRAY[]::text[] AS participated_event_ids")
    if "event_tags" in scholar_cols:
        fields.append("event_tags")
    else:
        fields.append("'[]'::jsonb AS event_tags")
    if "is_cobuild_scholar" in scholar_cols:
        fields.append("is_cobuild_scholar")
    else:
        fields.append("FALSE AS is_cobuild_scholar")
    if "custom_fields" in scholar_cols:
        fields.append("custom_fields")
    else:
        fields.append("'{}'::jsonb AS custom_fields")
    if "achievement_tags" in scholar_cols:
        fields.append("achievement_tags")
    else:
        fields.append("ARRAY[]::text[] AS achievement_tags")
    publication_table_sql = (
        "SELECT jsonb_agg("
        "jsonb_build_object("
        "'title', COALESCE(sp.title, ''), "
        "'venue', COALESCE(sp.venue, ''), "
        "'year', COALESCE(sp.year::text, ''), "
        "'authors', COALESCE(array_to_string(sp.authors, ', '), ''), "
        "'url', COALESCE(sp.url, ''), "
        "'citation_count', COALESCE(sp.citation_count, -1), "
        "'is_corresponding', COALESCE(sp.is_corresponding, FALSE), "
        "'added_by', COALESCE(sp.added_by, '')"
        ") ORDER BY sp.year DESC NULLS LAST, sp.created_at DESC, sp.id DESC"
        ") FROM scholar_publications sp WHERE sp.scholar_id = scholars.id"
    )
    if "representative_publications" in scholar_cols:
        fields.append(
            "COALESCE(NULLIF(representative_publications, '[]'::jsonb), "
            f"({publication_table_sql}), '[]'::jsonb) AS representative_publications"
        )
    else:
        fields.append(
            f"COALESCE(({publication_table_sql}), '[]'::jsonb) AS representative_publications"
        )
    award_table_sql = (
        "SELECT jsonb_agg("
        "jsonb_build_object("
        "'title', COALESCE(sa.title, ''), "
        "'year', COALESCE(sa.year::text, ''), "
        "'level', COALESCE(sa.level, ''), "
        "'grantor', COALESCE(sa.grantor, ''), "
        "'description', COALESCE(sa.description, ''), "
        "'added_by', COALESCE(sa.added_by, '')"
        ") ORDER BY sa.year DESC NULLS LAST, sa.created_at DESC, sa.id DESC"
        ") FROM scholar_awards sa WHERE sa.scholar_id = scholars.id"
    )
    if "awards" in scholar_cols:
        fields.append(
            "COALESCE(NULLIF(awards, '[]'::jsonb), "
            f"({award_table_sql}), '[]'::jsonb) AS awards"
        )
    else:
        fields.append(f"COALESCE(({award_table_sql}), '[]'::jsonb) AS awards")
    patent_table_sql = (
        "SELECT jsonb_agg("
        "jsonb_build_object("
        "'title', COALESCE(spt.title, ''), "
        "'patent_no', COALESCE(spt.patent_no, ''), "
        "'year', COALESCE(spt.year::text, ''), "
        "'inventors', COALESCE(array_to_string(spt.inventors, ', '), ''), "
        "'patent_type', COALESCE(spt.patent_type, ''), "
        "'status', COALESCE(spt.status, ''), "
        "'added_by', COALESCE(spt.added_by, '')"
        ") ORDER BY spt.year DESC NULLS LAST, spt.created_at DESC, spt.id DESC"
        ") FROM scholar_patents spt WHERE spt.scholar_id = scholars.id"
    )
    if "patents" in scholar_cols:
        fields.append(
            "COALESCE(NULLIF(patents, '[]'::jsonb), "
            f"({patent_table_sql}), '[]'::jsonb) AS patents"
        )
    else:
        fields.append(f"COALESCE(({patent_table_sql}), '[]'::jsonb) AS patents")
    fields.append(
        "EXISTS ("
        "SELECT 1 FROM supervised_students ss "
        "WHERE COALESCE(ss.scholar_id, '') = COALESCE(scholars.id, '')"
        ') AS "__has_supervised_students"'
    )

    return "SELECT\n    " + ",\n    ".join(fields) + "\nFROM scholars"


async def _resolve_institution_names_by_region_and_type(
    region: str | None,
    affiliation_type: str | None,
) -> set[str] | None:
    normalized_affiliation_type = normalize_org_type(affiliation_type)
    if not region and not normalized_affiliation_type:
        return None

    inst_map = await get_institution_classification_map()
    if not inst_map:
        return set()

    matched: set[str] = set()
    for name in inst_map:
        if region and _get_region(name, inst_map) != region:
            continue
        if normalized_affiliation_type and (
            normalize_org_type(_get_org_type(name, inst_map)) != normalized_affiliation_type
        ):
            continue
        matched.add(name)
    return matched


def _merge_allowed_universities(
    explicit_names: list[str] | None,
    derived_names: set[str] | None,
) -> list[str] | None:
    if explicit_names is None and derived_names is None:
        return None

    explicit = None if explicit_names is None else set(explicit_names)
    derived = derived_names

    if explicit is None:
        merged = derived or set()
    elif derived is None:
        merged = explicit
    else:
        merged = explicit & derived

    if not merged:
        return []
    return sorted(merged)


def _build_where_clause(
    *,
    university: str | None,
    department: str | None,
    position: str | None,
    is_academician: bool | None,
    is_potential_recruit: bool | None,
    is_advisor_committee: bool | None,
    is_adjunct_supervisor: bool | None,
    has_email: bool | None,
    keyword: str | None,
    is_chinese: bool | None,
    is_current_student: bool | None,
    chinese_identity: str | None,
    achievement_tag: str | None,
    achievement_tags: str | None,
    custom_field_key: str | None,
    custom_field_value: str | None,
    allowed_universities: list[str] | None,
) -> tuple[str, list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if allowed_universities is not None:
        params.append(allowed_universities)
        conditions.append(f"university = ANY(${len(params)}::text[])")

    if university:
        params.append(_normalize_exact_text(university))
        conditions.append(
            "LOWER(REGEXP_REPLACE(BTRIM(COALESCE(university, '')), '\\s+', ' ', 'g'))"
            f" = ${len(params)}"
        )

    if department:
        params.append(_normalize_exact_text(department))
        conditions.append(
            "LOWER(REGEXP_REPLACE(BTRIM(COALESCE(department, '')), '\\s+', ' ', 'g'))"
            f" = ${len(params)}"
        )

    if position:
        params.append(position)
        conditions.append(f"position = ${len(params)}")

    if is_academician is not None:
        params.append(is_academician)
        conditions.append(f"is_academician = ${len(params)}")

    if is_potential_recruit is not None:
        params.append(is_potential_recruit)
        conditions.append(f"is_potential_recruit = ${len(params)}")

    if is_advisor_committee is not None:
        params.append(is_advisor_committee)
        conditions.append(f"is_advisor_committee = ${len(params)}")

    if is_adjunct_supervisor is not None:
        if is_adjunct_supervisor:
            conditions.append("COALESCE(adjunct_supervisor->>'status', '') <> ''")
        else:
            conditions.append("COALESCE(adjunct_supervisor->>'status', '') = ''")

    if has_email is not None:
        if has_email:
            conditions.append("COALESCE(email, '') <> ''")
        else:
            conditions.append("COALESCE(email, '') = ''")

    if keyword and keyword.strip():
        params.append(f"%{keyword.strip().lower()}%")
        p = len(params)
        conditions.append(
            "("
            f"LOWER(COALESCE(name, '')) LIKE ${p} "
            f"OR LOWER(COALESCE(name_en, '')) LIKE ${p} "
            f"OR LOWER(COALESCE(bio, '')) LIKE ${p} "
            f"OR LOWER(COALESCE(array_to_string(research_areas, ' '), '')) LIKE ${p} "
            f"OR LOWER(COALESCE(array_to_string(keywords, ' '), '')) LIKE ${p}"
            ")"
        )

    if is_chinese is not None:
        params.append(str(is_chinese).lower())
        p = len(params)
        conditions.append(
            "("
            "COALESCE("
            "custom_fields #>> '{profile_flags,is_chinese}', "
            "custom_fields #>> '{metadata_profile,is_chinese}'"
            f") = ${p}"
            ")"
        )

    if is_current_student is not None:
        params.append(str(is_current_student).lower())
        p = len(params)
        conditions.append(
            "("
            "COALESCE("
            "custom_fields #>> '{profile_flags,is_current_student}', "
            "custom_fields #>> '{profile_flags,is_student}', "
            "custom_fields #>> '{metadata_profile,is_current_student}', "
            "custom_fields #>> '{metadata_profile,is_student}'"
            f") = ${p}"
            ")"
        )

    if chinese_identity and chinese_identity.strip().lower() in {"unknown", "待判定"}:
        conditions.append(
            "("
            "COALESCE("
            "custom_fields #>> '{profile_flags,is_chinese}', "
            "custom_fields #>> '{metadata_profile,is_chinese}'"
            ") IS NULL"
            ")"
        )

    raw_tag_targets = [
        tag.strip()
        for tag in (achievement_tags or "").replace("，", ",").split(",")
        if tag.strip()
    ]
    if achievement_tag and achievement_tag.strip():
        raw_tag_targets.append(achievement_tag.strip())
    raw_tag_targets = [tag for tag in dict.fromkeys(raw_tag_targets) if tag]
    tag_targets = parse_achievement_filter_tokens(raw_tag_targets)

    if tag_targets:
        venue_tags = [tag for tag, year in tag_targets if year is None]
        year_filters = [(tag, year) for tag, year in tag_targets if year is not None]
        tag_conditions: list[str] = []
        if venue_tags:
            params.append(venue_tags)
            tag_param = len(params)
            params.append([f"%{tag.lower()}%" for tag in venue_tags])
            like_param = len(params)
            tag_conditions.append(
                "("
                f"achievement_tags && ${tag_param}::text[] "
                "OR EXISTS ("
                "SELECT 1 FROM scholar_publications sp "
                "WHERE sp.scholar_id = scholars.id "
                f"AND LOWER(COALESCE(sp.venue, '')) LIKE ANY(${like_param}::text[])"
                ")"
                ")"
            )
        for tag, year in year_filters:
            params.append(f"%{tag.lower()}%")
            like_param = len(params)
            params.append(year)
            year_param = len(params)
            tag_conditions.append(
                "EXISTS ("
                "SELECT 1 FROM scholar_publications sp "
                "WHERE sp.scholar_id = scholars.id "
                f"AND LOWER(COALESCE(sp.venue, '')) LIKE ${like_param} "
                f"AND sp.year = ${year_param}"
                ")"
            )
        conditions.append("(" + " OR ".join(tag_conditions) + ")")

    if custom_field_key:
        params.append(custom_field_key)
        key_param = len(params)
        if custom_field_value is None:
            conditions.append(f"(custom_fields ->> ${key_param}) IS NULL")
        else:
            params.append(custom_field_value)
            value_param = len(params)
            conditions.append(
                f"COALESCE(custom_fields ->> ${key_param}, '') = ${value_param}"
            )

    if not conditions:
        return "", params
    return " WHERE " + " AND ".join(conditions), params


async def query_scholar_list_fast(
    *,
    university: str | None,
    department: str | None,
    position: str | None,
    is_academician: bool | None,
    is_potential_recruit: bool | None,
    is_advisor_committee: bool | None,
    is_adjunct_supervisor: bool | None,
    has_email: bool | None,
    keyword: str | None,
    community_name: str | None,
    community_type: str | None,
    project_category: str | None,
    project_subcategory: str | None,
    participated_event_id: str | None,
    is_cobuild_scholar: bool | None,
    region: str | None,
    affiliation_type: str | None,
    institution_names: list[str] | None,
    custom_field_key: str | None,
    custom_field_value: str | None,
    is_chinese: bool | None,
    is_current_student: bool | None,
    chinese_identity: str | None,
    achievement_tag: str | None,
    achievement_tags: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    if (
        community_name
        or community_type
        or
        project_category
        or project_subcategory
        or participated_event_id
        or is_cobuild_scholar is not None
    ):
        raise RuntimeError("community/project/event tag filters are handled by fallback query path")

    by_region_or_type = await _resolve_institution_names_by_region_and_type(
        region,
        affiliation_type,
    )
    allowed_universities = _merge_allowed_universities(
        institution_names,
        by_region_or_type,
    )
    if allowed_universities is not None and not allowed_universities:
        return {
            "total": 0,
            "page": 1,
            "page_size": page_size,
            "total_pages": 1,
            "items": [],
        }

    where_sql, params = _build_where_clause(
        university=university,
        department=department,
        position=position,
        is_academician=is_academician,
        is_potential_recruit=is_potential_recruit,
        is_advisor_committee=is_advisor_committee,
        is_adjunct_supervisor=is_adjunct_supervisor,
        has_email=has_email,
        keyword=keyword,
        is_chinese=is_chinese,
        is_current_student=is_current_student,
        chinese_identity=chinese_identity,
        achievement_tag=achievement_tag,
        achievement_tags=achievement_tags,
        custom_field_key=custom_field_key,
        custom_field_value=custom_field_value,
        allowed_universities=allowed_universities,
    )

    pool = get_pool()
    count_sql = f"SELECT COUNT(*)::bigint AS n FROM scholars{where_sql}"
    total = int(await pool.fetchval(count_sql, *params) or 0)
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    effective_page = min(max(page, 1), total_pages)

    offset = (effective_page - 1) * page_size
    data_params = [*params, page_size, offset]
    limit_param = len(data_params) - 1
    offset_param = len(data_params)
    list_select_sql = await _build_list_select_sql()
    data_sql = (
        f"{list_select_sql}{where_sql}"
        f" ORDER BY name ASC LIMIT ${limit_param} OFFSET ${offset_param}"
    )
    rows = [dict(r) for r in await pool.fetch(data_sql, *data_params)]

    all_annotations = annotation_store._load()
    for row in rows:
        url_hash = row.get("url_hash") or ""
        if url_hash and url_hash in all_annotations:
            _merge_annotation(row, all_annotations[url_hash])

    return {
        "total": total,
        "page": effective_page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": [_to_list_item(i) for i in rows],
    }
