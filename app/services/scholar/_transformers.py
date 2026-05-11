"""Response shape transformers — convert raw scholar dicts to API output shapes."""
from __future__ import annotations

import json
from typing import Any

from app.services.scholar._achievement_tags import extract_achievement_tags

_EMPTY_ADJUNCT: dict[str, str] = {
    "status": "", "type": "", "agreement_type": "", "agreement_period": "", "recommender": "",
}
_PROFILE_LINK_DEFAULTS: dict[str, Any] = {
    "homepage": "",
    "lab": "",
    "github": "",
    "linkedin": "",
    "google_scholar": "",
    "orcid": "",
    "dblp": "",
    "other": [],
}
_LEGACY_PROFILE_LINK_MAP: dict[str, str] = {
    "homepage": "profile_url",
    "lab": "lab_url",
    "google_scholar": "google_scholar_url",
    "dblp": "dblp_url",
    "orcid": "orcid",
}


def _coerce_adjunct_supervisor(raw: Any) -> dict[str, str]:
    """Normalize adjunct_supervisor field."""
    if isinstance(raw, dict):
        return {
            "status": raw.get("status", ""),
            "type": raw.get("type", ""),
            "agreement_type": raw.get("agreement_type", ""),
            "agreement_period": raw.get("agreement_period", ""),
            "recommender": raw.get("recommender", ""),
        }
    return dict(_EMPTY_ADJUNCT)


def _coerce_project_tags(
    raw: Any,
    *,
    legacy_category: str = "",
    legacy_subcategory: str = "",
) -> list[dict[str, str]]:
    tags: list[dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category") or "").strip()
            subcategory = str(item.get("subcategory") or "").strip()
            if not category and not subcategory:
                continue
            tags.append(
                {
                    "category": category,
                    "subcategory": subcategory,
                    "project_id": str(item.get("project_id") or ""),
                    "project_title": str(item.get("project_title") or ""),
                }
            )
    if tags:
        return tags

    return []


def _truthy_custom_field(custom_fields: dict[str, Any], key: str) -> bool:
    value = custom_fields.get(key)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def _has_adjunct_supervisor(item: dict[str, Any]) -> bool:
    adj = item.get("adjunct_supervisor")
    if isinstance(adj, dict):
        return bool(str(adj.get("status") or "").strip())
    return False


def _append_project_tag(
    tags: list[dict[str, str]],
    seen: set[tuple[str, str]],
    category: str,
    subcategory: str,
) -> None:
    key = (category, subcategory)
    if key in seen:
        return
    seen.add(key)
    tags.append(
        {
            "category": category,
            "subcategory": subcategory,
            "project_id": "",
            "project_title": "",
        }
    )


def _derive_project_tags_from_metadata(
    item: dict[str, Any],
    custom_fields: dict[str, Any],
) -> list[dict[str, str]]:
    tags: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    is_adjunct = (
        _has_adjunct_supervisor(item)
        or _truthy_custom_field(custom_fields, "education_training_adjunct")
        or _truthy_custom_field(custom_fields, "aaai_plus_adjunct_mapped")
    )
    if is_adjunct:
        _append_project_tag(tags, seen, "教育培养", "兼职导师")
    if _truthy_custom_field(custom_fields, "mentor_is_school_mentor"):
        _append_project_tag(tags, seen, "教育培养", "学院学生高校导师")
    if item.get("__has_supervised_students") and not is_adjunct:
        _append_project_tag(tags, seen, "教育培养", "全职导师")
    return tags


def _merge_project_tags(
    raw: Any,
    *,
    custom_fields: dict[str, Any],
    item: dict[str, Any],
    legacy_category: str = "",
    legacy_subcategory: str = "",
) -> list[dict[str, str]]:
    tags = _coerce_project_tags(
        raw,
        legacy_category=legacy_category,
        legacy_subcategory=legacy_subcategory,
    )
    seen = {
        (str(tag.get("category") or ""), str(tag.get("subcategory") or ""))
        for tag in tags
    }
    for tag in _derive_project_tags_from_metadata(item, custom_fields):
        _append_project_tag(
            tags,
            seen,
            str(tag.get("category") or ""),
            str(tag.get("subcategory") or ""),
        )
    return tags


def _coerce_event_tags(raw: Any) -> list[dict[str, str]]:
    tags: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return tags
    for item in raw:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").strip()
        series = str(item.get("series") or "").strip()
        event_type = str(item.get("event_type") or "").strip()
        if not category and not series and not event_type:
            continue
        tags.append(
            {
                "category": category,
                "series": series,
                "event_type": event_type,
                "event_id": str(item.get("event_id") or ""),
                "event_title": str(item.get("event_title") or ""),
            }
        )
    return tags


def _is_cobuild_scholar(
    item: dict[str, Any],
    project_tags: list[dict[str, str]],
    event_tags: list[dict[str, str]],
) -> bool:
    # Project tags are the source of truth for co-build relationship.
    if project_tags:
        return True
    explicit = item.get("is_cobuild_scholar")
    if isinstance(explicit, bool):
        return explicit
    return False


def _coerce_custom_fields(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _coerce_list(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except Exception:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _to_text(value: Any) -> str:
    return "" if value is None else str(value)


def _join_text_items(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(
            text for item in value if (text := str(item or "").strip())
        )
    return _to_text(value)


def _to_int(value: Any, *, default: int = -1) -> int:
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _normalize_publication_records(raw: list[Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        records.append(
            {
                "title": _to_text(item.get("title")),
                "venue": _to_text(item.get("venue")),
                "year": _to_text(item.get("year")),
                "authors": _join_text_items(item.get("authors")),
                "url": _to_text(item.get("url")),
                "doi": _to_text(item.get("doi")),
                "abstract": _to_text(item.get("abstract")),
                "publication_date": _to_text(item.get("publication_date")),
                "project_group_name": _to_text(item.get("project_group_name")),
                "source_type": _to_text(item.get("source_type")),
                "citation_count": _to_int(item.get("citation_count")),
                "is_corresponding": _to_bool(item.get("is_corresponding")),
                "added_by": _to_text(item.get("added_by")) or "crawler",
            }
        )
    return records


def _normalize_patent_records(raw: list[Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        records.append(
            {
                "title": _to_text(item.get("title")),
                "patent_no": _to_text(item.get("patent_no")),
                "year": _to_text(item.get("year")),
                "inventors": _join_text_items(item.get("inventors")),
                "patent_type": _to_text(item.get("patent_type")),
                "status": _to_text(item.get("status")),
                "added_by": _to_text(item.get("added_by")) or "crawler",
            }
        )
    return records


def _normalize_award_records(raw: list[Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        records.append(
            {
                "title": _to_text(item.get("title")),
                "year": _to_text(item.get("year")),
                "level": _to_text(item.get("level")),
                "grantor": _to_text(item.get("grantor")),
                "description": _to_text(item.get("description")),
                "added_by": _to_text(item.get("added_by")) or "crawler",
            }
        )
    return records


def _normalize_education_records(raw: list[Any]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        year = item.get("year")
        if year is None:
            year = item.get("end_year")
        records.append(
            {
                "degree": _to_text(item.get("degree")),
                "institution": _to_text(item.get("institution")),
                "year": _to_text(year),
                "major": _to_text(item.get("major")),
            }
        )
    return records


def _normalize_profile_links(raw: Any) -> dict[str, Any]:
    links = dict(_PROFILE_LINK_DEFAULTS)
    value = raw
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, dict):
        return links

    for key in ("homepage", "lab", "github", "linkedin", "google_scholar", "orcid", "dblp"):
        links[key] = str(value.get(key) or "").strip()

    other = value.get("other")
    if isinstance(other, list):
        links["other"] = [str(item).strip() for item in other if str(item).strip()]
    return links


def _profile_links_from_legacy_fields(item: dict[str, Any]) -> dict[str, Any]:
    links = {
        "homepage": str(item.get("profile_url") or "").strip(),
        "lab": str(item.get("lab_url") or "").strip(),
        "github": "",
        "linkedin": "",
        "google_scholar": str(item.get("google_scholar_url") or "").strip(),
        "orcid": str(item.get("orcid") or "").strip(),
        "dblp": "",
        "other": [],
    }
    legacy_dblp = str(item.get("dblp_url") or "").strip()
    legacy_dblp_lower = legacy_dblp.lower()
    if "github.com" in legacy_dblp_lower:
        links["github"] = legacy_dblp
    elif "linkedin.com" in legacy_dblp_lower:
        links["linkedin"] = legacy_dblp
    elif "dblp.org" in legacy_dblp_lower:
        links["dblp"] = legacy_dblp
    elif legacy_dblp:
        links["other"] = [legacy_dblp]
    return links


def _build_profile_links(
    item: dict[str, Any],
    custom_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    legacy_links = _profile_links_from_legacy_fields(item)
    custom_links = _normalize_profile_links((custom_fields or {}).get("profile_links"))

    merged = dict(legacy_links)
    for key in ("homepage", "lab", "github", "linkedin", "google_scholar", "orcid", "dblp"):
        if custom_links.get(key):
            merged[key] = custom_links[key]
    if custom_links.get("other"):
        merged["other"] = custom_links["other"]
    return merged


def _profile_links_to_legacy_fields(profile_links: dict[str, Any]) -> dict[str, str]:
    return {
        legacy_key: str(profile_links.get(profile_key) or "").strip()
        for profile_key, legacy_key in _LEGACY_PROFILE_LINK_MAP.items()
    }


def _to_list_item(item: dict[str, Any]) -> dict[str, Any]:
    custom_fields = _coerce_custom_fields(item.get("custom_fields"))
    profile_links = _build_profile_links(item, custom_fields)
    legacy_profile_fields = _profile_links_to_legacy_fields(profile_links)
    representative_publications = _normalize_publication_records(
        _coerce_list(item.get("representative_publications"))
    )
    awards = _normalize_award_records(_coerce_list(item.get("awards")))
    achievement_tags = extract_achievement_tags(
        achievement_tags=item.get("achievement_tags"),
        representative_publications=[
            pub for pub in representative_publications if isinstance(pub, dict)
        ],
        awards=[award for award in awards if isinstance(award, dict)],
        scholar_activities=[
            activity
            for activity in _coerce_list(item.get("scholar_activities"))
            if isinstance(activity, (dict, str))
        ],
    )
    project_tags = _merge_project_tags(
        item.get("project_tags"),
        custom_fields=custom_fields,
        item=item,
        legacy_category=str(item.get("project_category") or ""),
        legacy_subcategory=str(item.get("project_subcategory") or ""),
    )
    participated_event_ids = item.get("participated_event_ids") or []
    event_tags = _coerce_event_tags(item.get("event_tags"))
    return {
        # DB rows commonly use `id` as the canonical scholar key.
        # Fallback to id when legacy payload misses `url_hash`.
        "url_hash": item.get("url_hash") or item.get("id") or "",
        "name": item.get("name") or "",
        "name_en": item.get("name_en") or "",
        "photo_url": item.get("photo_url") or "",
        "university": item.get("university") or "",
        "department": item.get("department") or "",
        "position": item.get("position") or "",
        "academic_titles": item.get("academic_titles") or [],
        "is_academician": bool(item.get("is_academician", False)),
        "research_areas": item.get("research_areas") or [],
        "email": item.get("email") or "",
        "profile_url": legacy_profile_fields["profile_url"],
        "profile_links": profile_links,
        "custom_fields": custom_fields,
        "achievement_tags": achievement_tags,
        "representative_publications": representative_publications,
        "awards": awards,
        "is_potential_recruit": bool(item.get("is_potential_recruit", False)),
        "is_advisor_committee": bool(item.get("is_advisor_committee", False)),
        "adjunct_supervisor": _coerce_adjunct_supervisor(item.get("adjunct_supervisor")),
        "is_cobuild_scholar": _is_cobuild_scholar(item, project_tags, event_tags),
        "project_tags": project_tags,
        "participated_event_ids": participated_event_ids,
        "event_tags": event_tags,
    }


def _to_detail(item: dict[str, Any]) -> dict[str, Any]:
    custom_fields = _coerce_custom_fields(item.get("custom_fields"))
    profile_links = _build_profile_links(item, custom_fields)
    legacy_profile_fields = _profile_links_to_legacy_fields(profile_links)
    representative_publications = _normalize_publication_records(
        _coerce_list(item.get("representative_publications"))
    )
    awards = _normalize_award_records(_coerce_list(item.get("awards")))
    patents = _normalize_patent_records(_coerce_list(item.get("patents")))
    achievement_tags = extract_achievement_tags(
        achievement_tags=item.get("achievement_tags"),
        representative_publications=[
            pub for pub in representative_publications if isinstance(pub, dict)
        ],
        awards=[award for award in awards if isinstance(award, dict)],
        scholar_activities=[
            activity
            for activity in _coerce_list(item.get("scholar_activities"))
            if isinstance(activity, (dict, str))
        ],
    )
    scholar_activities = [
        activity
        for activity in _coerce_list(item.get("scholar_activities"))
        if isinstance(activity, dict)
    ]
    project_tags = _merge_project_tags(
        item.get("project_tags"),
        custom_fields=custom_fields,
        item=item,
        legacy_category=str(item.get("project_category") or ""),
        legacy_subcategory=str(item.get("project_subcategory") or ""),
    )
    event_tags = _coerce_event_tags(item.get("event_tags"))
    return {
        # DB rows commonly use `id` as the canonical scholar key.
        # Fallback to id when legacy payload misses `url_hash`.
        "url_hash": item.get("url_hash") or item.get("id") or "",
        "url": item.get("url") or "",
        "content": item.get("content") or "",
        "name": item.get("name") or "",
        "name_en": item.get("name_en") or "",
        "gender": item.get("gender") or "",
        "photo_url": item.get("photo_url") or "",
        "university": item.get("university") or "",
        "department": item.get("department") or "",
        "secondary_departments": item.get("secondary_departments") or [],
        "position": item.get("position") or "",
        "academic_titles": item.get("academic_titles") or [],
        "is_academician": bool(item.get("is_academician", False)),
        "research_areas": item.get("research_areas") or [],
        "keywords": item.get("keywords") or [],
        "bio": item.get("bio") or "",
        "bio_en": item.get("bio_en") or "",
        "email": item.get("email") or "",
        "phone": item.get("phone") or "",
        "office": item.get("office") or "",
        "profile_url": legacy_profile_fields["profile_url"],
        "lab_url": legacy_profile_fields["lab_url"],
        "google_scholar_url": legacy_profile_fields["google_scholar_url"],
        "dblp_url": legacy_profile_fields["dblp_url"],
        "orcid": legacy_profile_fields["orcid"],
        "profile_links": profile_links,
        "phd_institution": item.get("phd_institution") or "",
        "phd_year": str(item.get("phd_year") or ""),
        "education": _normalize_education_records(_coerce_list(item.get("education"))),
        "publications_count": item.get("publications_count") or -1,
        "h_index": item.get("h_index") or -1,
        "citations_count": item.get("citations_count") or -1,
        "metrics_updated_at": item.get("metrics_updated_at") or "",
        "achievement_tags": achievement_tags,
        "representative_publications": representative_publications,
        "patents": patents,
        "awards": awards,
        "scholar_activities": scholar_activities,
        "is_advisor_committee": bool(item.get("is_advisor_committee", False)),
        "adjunct_supervisor": _coerce_adjunct_supervisor(item.get("adjunct_supervisor")),
        "supervised_students": item.get("supervised_students") or [],
        "joint_research_projects": item.get("joint_research_projects") or [],
        "joint_management_roles": item.get("joint_management_roles") or [],
        "academic_exchange_records": item.get("academic_exchange_records") or [],
        "participated_event_ids": item.get("participated_event_ids") or [],
        "event_tags": event_tags,
        "project_tags": project_tags,
        "is_cobuild_scholar": _is_cobuild_scholar(item, project_tags, event_tags),
        "is_potential_recruit": bool(item.get("is_potential_recruit", False)),
        "institute_relation_notes": item.get("institute_relation_notes") or "",
        "relation_updated_by": item.get("relation_updated_by") or "",
        "relation_updated_at": item.get("relation_updated_at") or "",
        "recent_updates": [],
        "tags": item.get("tags") or [],
        "custom_fields": custom_fields,
    }
