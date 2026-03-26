"""Fast SQL-backed query helpers for scholar list/detail endpoints."""
from __future__ import annotations

import math
from typing import Any

from app.db.pool import get_pool
from app.services.scholar._data import _merge_annotation
from app.services.scholar._filters import (
    _get_org_type,
    _get_region,
    get_institution_classification_map,
)
from app.services.scholar._transformers import _to_list_item
from app.services.stores import scholar_annotation_store as annotation_store

_LIST_SELECT_SQL = """
SELECT
    id AS url_hash,
    name,
    name_en,
    photo_url,
    university,
    department,
    position,
    academic_titles,
    is_academician,
    research_areas,
    email,
    profile_url,
    is_potential_recruit,
    is_advisor_committee,
    adjunct_supervisor
FROM scholars
"""


async def _resolve_institution_names_by_region_and_type(
    region: str | None,
    affiliation_type: str | None,
) -> set[str] | None:
    if not region and not affiliation_type:
        return None

    inst_map = await get_institution_classification_map()
    if not inst_map:
        return set()

    matched: set[str] = set()
    for name in inst_map:
        if region and _get_region(name, inst_map) != region:
            continue
        if affiliation_type and _get_org_type(name, inst_map) != affiliation_type:
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
        params.append(f"%{university}%")
        conditions.append(f"university ILIKE ${len(params)}")

    if department:
        params.append(f"%{department}%")
        conditions.append(f"department ILIKE ${len(params)}")

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
    region: str | None,
    affiliation_type: str | None,
    institution_names: list[str] | None,
    custom_field_key: str | None,
    custom_field_value: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
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
            "page": page,
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
        custom_field_key=custom_field_key,
        custom_field_value=custom_field_value,
        allowed_universities=allowed_universities,
    )

    pool = get_pool()
    count_sql = f"SELECT COUNT(*)::bigint AS n FROM scholars{where_sql}"
    total = int(await pool.fetchval(count_sql, *params) or 0)

    offset = (page - 1) * page_size
    data_params = [*params, page_size, offset]
    limit_param = len(data_params) - 1
    offset_param = len(data_params)
    data_sql = (
        f"{_LIST_SELECT_SQL}{where_sql}"
        f" ORDER BY name ASC LIMIT ${limit_param} OFFSET ${offset_param}"
    )
    rows = [dict(r) for r in await pool.fetch(data_sql, *data_params)]

    all_annotations = annotation_store._load()
    for row in rows:
        url_hash = row.get("url_hash") or ""
        if url_hash and url_hash in all_annotations:
            _merge_annotation(row, all_annotations[url_hash])

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": [_to_list_item(i) for i in rows],
    }
