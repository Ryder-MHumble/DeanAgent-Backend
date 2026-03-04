"""Filtering helpers for faculty queries."""
from __future__ import annotations

from typing import Any


def _match_fuzzy(value: str, query: str) -> bool:
    return query.strip().lower() in (value or "").lower()


def _apply_filters(
    items: list[dict[str, Any]],
    *,
    university: str | None,
    department: str | None,
    group: str | None,
    position: str | None,
    is_academician: bool | None,
    is_potential_recruit: bool | None,
    is_advisor_committee: bool | None,
    has_email: bool | None,
    min_completeness: int | None,
    keyword: str | None,
    source_filter: set[str] | None,
) -> list[dict[str, Any]]:
    result = items

    if source_filter is not None:
        result = [i for i in result if i.get("source_id", "") in source_filter]

    if group:
        result = [i for i in result if i.get("group", "") == group]

    if university:
        result = [i for i in result if _match_fuzzy(i.get("university", ""), university)]

    if department:
        result = [i for i in result if _match_fuzzy(i.get("department", ""), department)]

    if position:
        result = [i for i in result if i.get("position", "") == position]

    if is_academician is not None:
        result = [i for i in result if bool(i.get("is_academician", False)) == is_academician]

    if is_potential_recruit is not None:
        result = [
            i for i in result
            if bool(i.get("is_potential_recruit", False)) == is_potential_recruit
        ]

    if is_advisor_committee is not None:
        result = [
            i for i in result
            if bool(i.get("is_advisor_committee", False)) == is_advisor_committee
        ]

    if has_email is not None:
        result = [i for i in result if bool(i.get("email", "")) == has_email]

    if min_completeness is not None:
        result = [i for i in result if (i.get("data_completeness") or 0) >= min_completeness]

    if keyword:
        kw = keyword.strip().lower()

        def _matches(i: dict[str, Any]) -> bool:
            if kw in (i.get("name") or "").lower():
                return True
            if kw in (i.get("name_en") or "").lower():
                return True
            if kw in (i.get("bio") or "").lower():
                return True
            if any(kw in area.lower() for area in (i.get("research_areas") or [])):
                return True
            if any(kw in kw_tag.lower() for kw_tag in (i.get("keywords") or [])):
                return True
            return False

        result = [i for i in result if _matches(i)]

    return result
