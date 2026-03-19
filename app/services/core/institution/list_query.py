"""List query and filtering logic for institutions.

Provides unified query interface supporting both flat and hierarchy views.
"""

from __future__ import annotations

from collections import defaultdict

from app.schemas.institution import InstitutionListResponse
from app.services.core.institution.detail_builder import build_list_item
from app.services.core.institution.sorting import sort_institutions
from app.services.core.institution.storage import fetch_all_institutions


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
        return await _get_hierarchy_view(
            region=region,
            org_type=org_type,
            classification=classification,
            is_adjunct_supervisor=is_adjunct_supervisor,
        )
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

    # Build hierarchy
    result_orgs = []
    for org in sorted_orgs:
        org_id = org["id"]
        org_name = org["name"]

        # Find departments for this organization
        departments = [
            rec for rec in all_records if rec.get("parent_id") == org_id
        ]
        sorted_depts = sort_institutions(departments)

        # Build organization item with departments
        org_item = build_list_item(org).model_dump()

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
    from app.services.scholar._data import _load_all_with_annotations_async

    # Fetch all scholars
    all_scholars = await _load_all_with_annotations_async()

    # Filter by adjunct supervisor status
    if is_adjunct_supervisor:
        def _has_adjunct(scholar: dict) -> bool:
            adj = scholar.get("adjunct_supervisor")
            if isinstance(adj, dict):
                return bool(adj.get("status", ""))
            return False
        filtered_scholars = [s for s in all_scholars if _has_adjunct(s)]
    else:
        filtered_scholars = all_scholars

    # Count by university and department
    counts: dict[tuple, int] = defaultdict(int)

    for scholar in filtered_scholars:
        university = scholar.get("university", "")
        department = scholar.get("department", "")

        if university:
            # Count for organization
            counts[("org", university)] += 1

            # Count for department
            if department:
                counts[("dept", university, department)] += 1

    return dict(counts)
