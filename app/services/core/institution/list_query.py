"""List query and filtering logic for institutions.

Provides unified query interface supporting both flat and hierarchy views.
"""

from __future__ import annotations

from collections import defaultdict
from time import monotonic

from app.schemas.institution import InstitutionListResponse
from app.services.core.institution.detail_builder import build_list_item
from app.services.core.institution.sorting import sort_institutions
from app.services.core.institution.storage import fetch_all_institutions

_HIERARCHY_CACHE_TTL_SECONDS = 30.0
_hierarchy_cache: dict[tuple[str | None, str | None, str | None, bool | None], tuple[float, dict]] = {}


async def get_institutions_unified(
    view: str = "flat",
    entity_type: str | None = None,
    region: str | None = None,
    org_type: str | None = None,
    classification: str | None = None,
    sub_classification: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    is_adjunct_supervisor: bool | None = None,
) -> InstitutionListResponse | dict:
    """Unified institution query interface.

    Args:
        view: View type ("flat" for list, "hierarchy" for tree structure)
        entity_type: Filter by entity type (organization/department)
        region: Filter by region (国内/国际)
        org_type: Filter by org type (高校/企业/研究机构/行业学会/其他)
        classification: Filter by classification (共建高校/兄弟院校/海外高校/其他高校)
        keyword: Search keyword (matches id or name)
        page: Page number (1-indexed)
        page_size: Items per page
        is_adjunct_supervisor: Filter scholars by adjunct supervisor status

    Returns:
        InstitutionListResponse for flat view, dict for hierarchy view
    """
    if view == "hierarchy":
        cache_key = (region, org_type, classification, is_adjunct_supervisor)
        now = monotonic()
        cached = _hierarchy_cache.get(cache_key)
        if cached and (now - cached[0]) < _HIERARCHY_CACHE_TTL_SECONDS:
            return cached[1]

        result = await _get_hierarchy_view(
            region=region,
            org_type=org_type,
            classification=classification,
            is_adjunct_supervisor=is_adjunct_supervisor,
        )
        _hierarchy_cache[cache_key] = (now, result)
        return result
    else:
        return await _get_flat_view(
            entity_type=entity_type,
            region=region,
            org_type=org_type,
            classification=classification,
            sub_classification=sub_classification,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )


async def _get_flat_view(
    entity_type: str | None = None,
    region: str | None = None,
    org_type: str | None = None,
    classification: str | None = None,
    sub_classification: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> InstitutionListResponse:
    """Get flat list view of institutions.

    Args:
        entity_type: Filter by entity type
        region: Filter by region
        org_type: Filter by org type
        classification: Filter by classification
        keyword: Search keyword
        page: Page number
        page_size: Items per page

    Returns:
        InstitutionListResponse with paginated results
    """
    # Fetch all records
    all_records = await fetch_all_institutions()

    # Apply filters
    filtered = _apply_filters(
        all_records,
        entity_type=entity_type,
        region=region,
        org_type=org_type,
        classification=classification,
        sub_classification=sub_classification,
        keyword=keyword,
    )

    # Sort
    sorted_records = sort_institutions(filtered)

    # Paginate
    total = len(sorted_records)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_records = sorted_records[start_idx:end_idx]

    # Build response items
    items = [build_list_item(rec) for rec in page_records]

    return InstitutionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
        items=items,
    )


async def _get_hierarchy_view(
    region: str | None = None,
    org_type: str | None = None,
    classification: str | None = None,
    is_adjunct_supervisor: bool | None = None,
) -> dict:
    """Get hierarchy view of institutions (organizations with nested departments).

    Args:
        region: Filter by region
        org_type: Filter by org type
        classification: Filter by classification
        is_adjunct_supervisor: Filter scholars by adjunct supervisor status

    Returns:
        Dict with organizations list, each containing nested departments
    """
    # Fetch all records
    all_records = await fetch_all_institutions()

    # Filter organizations
    organizations = _apply_filters(
        all_records,
        entity_type="organization",
        region=region,
        org_type=org_type,
        classification=classification,
    )

    # Sort organizations
    sorted_orgs = sort_institutions(organizations)

    # If is_adjunct_supervisor filter is active, we need to recount scholars
    scholar_counts = None
    if is_adjunct_supervisor is not None:
        scholar_counts = await _count_scholars_by_institution(is_adjunct_supervisor)

    # Build parent_id -> departments map once (avoid O(org * all_records) scans).
    departments_by_parent: dict[str, list[dict]] = defaultdict(list)
    for rec in all_records:
        parent_id = rec.get("parent_id")
        if parent_id:
            departments_by_parent[parent_id].append(rec)

    # Build hierarchy
    result_orgs = []
    for org in sorted_orgs:
        org_id = org["id"]
        org_name = org["name"]

        # Departments under current organization
        departments = departments_by_parent.get(org_id, [])
        sorted_depts = sort_institutions(departments)

        # Keep hierarchy payload lean for scholar page sidebar.
        org_item = {
            "id": org["id"],
            "name": org["name"],
            "entity_type": org.get("entity_type"),
            "region": org.get("region"),
            "org_type": org.get("org_type"),
            "classification": org.get("classification"),
            "sub_classification": org.get("sub_classification"),
        }

        # Override scholar_count if filtering by is_adjunct_supervisor
        if scholar_counts is not None:
            org_scholar_count = scholar_counts.get(("org", org_name), 0)
            org_item["scholar_count"] = org_scholar_count

            org_item["departments"] = [
                {
                    "id": dept["id"],
                    "name": dept["name"],
                    "scholar_count": scholar_counts.get(("dept", org_name, dept["name"]), 0),
                }
                for dept in sorted_depts
            ]
        else:
            org_item["departments"] = [
                {
                    "id": dept["id"],
                    "name": dept["name"],
                    "scholar_count": dept.get("scholar_count", 0),
                }
                for dept in sorted_depts
            ]

        result_orgs.append(org_item)

    return {"organizations": result_orgs}


def _apply_filters(
    records: list[dict],
    entity_type: str | None = None,
    region: str | None = None,
    org_type: str | None = None,
    classification: str | None = None,
    sub_classification: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    """Apply filters to institution records.

    Args:
        records: List of institution records
        entity_type: Filter by entity type
        region: Filter by region
        org_type: Filter by org type
        classification: Filter by classification
        keyword: Search keyword

    Returns:
        Filtered list of records
    """
    filtered = records

    if entity_type:
        filtered = [r for r in filtered if r.get("entity_type") == entity_type]

    if region:
        filtered = [r for r in filtered if r.get("region") == region]

    if org_type:
        filtered = [r for r in filtered if r.get("org_type") == org_type]

    if classification:
        filtered = [r for r in filtered if r.get("classification") == classification]

    if sub_classification:
        filtered = [r for r in filtered if r.get("sub_classification") == sub_classification]

    if keyword:
        keyword_lower = keyword.lower()
        filtered = [
            r
            for r in filtered
            if keyword_lower in r["id"].lower() or keyword_lower in r["name"].lower()
        ]

    return filtered


async def _count_scholars_by_institution(is_adjunct_supervisor: bool) -> dict[tuple, int]:
    """Count scholars by university and department with adjunct supervisor filter.

    Args:
        is_adjunct_supervisor: Whether to count only adjunct supervisors

    Returns:
        Dict mapping (type, university[, department]) to scholar count
        - ("org", "上海交通大学") -> count for university
        - ("dept", "上海交通大学", "计算机系") -> count for department
    """
    from app.db.pool import get_pool

    # SQL aggregation is far faster than loading all scholars into Python.
    where_sql = (
        "WHERE COALESCE(university, '') <> ''"
        + (" AND COALESCE(adjunct_supervisor->>'status', '') <> ''" if is_adjunct_supervisor else "")
    )
    sql = f"""
        SELECT
            university,
            department,
            COUNT(*)::int AS scholar_count
        FROM scholars
        {where_sql}
        GROUP BY university, department
    """
    rows = await get_pool().fetch(sql)

    counts: dict[tuple, int] = defaultdict(int)
    for row in rows:
        university = row.get("university") or ""
        if not university:
            continue
        department = row.get("department") or ""
        c = int(row.get("scholar_count") or 0)
        counts[("org", university)] += c
        if department:
            counts[("dept", university, department)] += c

    return dict(counts)
