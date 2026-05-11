from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from app.schemas.openreview_author import OpenReviewAuthorProfile

SORT_COLUMNS = {
    "publication_count": "publication_count",
    "updated_at": "updated_at",
    "preferred_name": "preferred_name",
}


def _clean_text(value: Any) -> str:
    return str(value or "").replace("\x00", "").strip()


def _copy_default(default: Any) -> Any:
    if isinstance(default, list):
        return list(default)
    if isinstance(default, dict):
        return dict(default)
    return default


def _decode_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        token = value.strip()
        if not token:
            return None
        try:
            return json.loads(token)
        except json.JSONDecodeError:
            return None
    return None


def _json_or_default(value: Any, default: Any) -> Any:
    decoded = _decode_json(value)
    if isinstance(decoded, (dict, list)):
        return decoded
    return _copy_default(default)


def _list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        token = value.strip()
        if not token:
            return []
        try:
            decoded = json.loads(token)
        except json.JSONDecodeError:
            return [token]
        value = decoded
    if not isinstance(value, (list, tuple, set)):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    token = _clean_text(value)
    return token or None


def _row_to_profile(row: Any) -> dict[str, Any]:
    payload = dict(row)
    return OpenReviewAuthorProfile(
        profile_id=_clean_text(payload.get("profile_id")),
        profile_url=_clean_text(payload.get("profile_url")) or None,
        canonical_profile_id=_clean_text(payload.get("canonical_profile_id")) or None,
        requested_profile_ids=_list_of_strings(payload.get("requested_profile_ids")),
        preferred_name=_clean_text(payload.get("preferred_name")) or None,
        names=_json_or_default(payload.get("names"), []),
        preferred_email=_clean_text(payload.get("preferred_email")) or None,
        emails=_list_of_strings(payload.get("emails")),
        personal_links=_json_or_default(payload.get("personal_links"), []),
        homepage_url=_clean_text(payload.get("homepage_url")) or None,
        google_scholar_url=_clean_text(payload.get("google_scholar_url")) or None,
        dblp_url=_clean_text(payload.get("dblp_url")) or None,
        linkedin_url=_clean_text(payload.get("linkedin_url")) or None,
        orcid=_clean_text(payload.get("orcid")) or None,
        semantic_scholar_url=_clean_text(payload.get("semantic_scholar_url")) or None,
        current_affiliation=_json_or_default(payload.get("current_affiliation"), {}),
        university=_clean_text(payload.get("university")) or None,
        department=_clean_text(payload.get("department")) or None,
        position=_clean_text(payload.get("position")) or None,
        career_history=_json_or_default(payload.get("career_history"), []),
        education=_json_or_default(payload.get("education"), []),
        expertise=_json_or_default(payload.get("expertise"), {}),
        keywords=_list_of_strings(payload.get("keywords")),
        relations=_json_or_default(payload.get("relations"), {}),
        publications=_json_or_default(payload.get("publications"), []),
        publication_count=int(payload.get("publication_count") or 0),
        source_author_rows=_json_or_default(payload.get("source_author_rows"), []),
        raw_profile=_json_or_default(payload.get("raw_profile"), None),
        raw_publication_notes=_json_or_default(payload.get("raw_publication_notes"), None),
        crawl_status=_clean_text(payload.get("crawl_status")) or None,
        crawl_error=_clean_text(payload.get("crawl_error")) or None,
        first_seen_at=_to_iso(payload.get("first_seen_at")),
        last_seen_at=_to_iso(payload.get("last_seen_at")),
        crawled_at=_to_iso(payload.get("crawled_at")),
        created_at=_to_iso(payload.get("created_at")),
        updated_at=_to_iso(payload.get("updated_at")),
    ).model_dump(mode="json")


async def list_openreview_authors(
    pool: Any,
    *,
    q: str | None = None,
    university: str | None = None,
    department: str | None = None,
    crawl_status: str | None = None,
    min_publication_count: int | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "publication_count",
    order: str = "desc",
) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []

    def add_clause(sql: str, value: Any) -> None:
        params.append(value)
        clauses.append(sql.format(len(params)))

    q_token = _clean_text(q)
    if q_token:
        params.append(f"%{q_token}%")
        placeholder = f"${len(params)}"
        clauses.append(
            "("
            f"COALESCE(a.profile_id, '') ILIKE {placeholder} OR "
            f"COALESCE(a.preferred_name, '') ILIKE {placeholder} OR "
            f"COALESCE(a.university, '') ILIKE {placeholder} OR "
            f"COALESCE(a.department, '') ILIKE {placeholder} OR "
            f"COALESCE(a.keywords::text, '') ILIKE {placeholder}"
            ")"
        )
    if university:
        add_clause("COALESCE(a.university, '') ILIKE ${}", f"%{_clean_text(university)}%")
    if department:
        add_clause("COALESCE(a.department, '') ILIKE ${}", f"%{_clean_text(department)}%")
    if crawl_status:
        add_clause("a.crawl_status = ${}", _clean_text(crawl_status))
    if min_publication_count is not None:
        add_clause("COALESCE(a.publication_count, 0) >= ${}", int(min_publication_count))

    page = max(int(page), 1)
    page_size = min(max(int(page_size), 1), 100)
    offset = (page - 1) * page_size
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sort_column = SORT_COLUMNS.get(_clean_text(sort_by), "publication_count")
    sort_order = "ASC" if _clean_text(order).lower() == "asc" else "DESC"

    total = await pool.fetchval(
        f"SELECT COUNT(*)::int FROM public.openreview_authors a {where_sql}",
        *params,
    )
    rows = await pool.fetch(
        f"""
        SELECT a.*
        FROM public.openreview_authors a
        {where_sql}
        ORDER BY a.{sort_column} {sort_order} NULLS LAST, a.profile_id ASC
        LIMIT ${len(params) + 1}
        OFFSET ${len(params) + 2}
        """,
        *params,
        page_size,
        offset,
    )
    return {
        "items": [_row_to_profile(row) for row in rows],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
    }


async def get_openreview_author(pool: Any, profile_id: str) -> dict[str, Any] | None:
    row = await pool.fetchrow(
        "SELECT * FROM public.openreview_authors WHERE profile_id = $1",
        _clean_text(profile_id),
    )
    if row is None:
        return None
    return _row_to_profile(row)
