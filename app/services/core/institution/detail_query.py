"""Detail query logic for individual institutions.

Fetches and builds detailed information for a single institution.
"""

from __future__ import annotations

from app.db.pool import get_pool
from app.schemas.institution import InstitutionDetailResponse
from app.services.core.institution.detail_builder import build_detail_response
from app.services.core.institution.storage import fetch_all_institutions, fetch_institution_by_id


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


async def _load_student_metrics_for_institution(
    institution_name: str,
    *,
    org_name: str | None = None,
) -> dict[str, int]:
    pool = get_pool()
    names = [_normalize_text(institution_name), _normalize_text(org_name)]
    names = [name for name in names if name]

    if not names:
        return {
            "student_count_24": 0,
            "student_count_25": 0,
            "student_count_total": 0,
        }

    row = await pool.fetchrow(
        """
        SELECT
          COUNT(*) FILTER (WHERE enrollment_year = 2024) AS student_count_24,
          COUNT(*) FILTER (WHERE enrollment_year = 2025) AS student_count_25,
          COUNT(*) AS student_count_total
        FROM supervised_students
        WHERE COALESCE(home_university, '') = ANY($1::text[])
        """,
        names,
    )

    total = int((row or {}).get("student_count_total") or 0)
    if total == 0:
        row = await pool.fetchrow(
            """
            SELECT
              COUNT(*) FILTER (WHERE enrollment_year = 2024) AS student_count_24,
              COUNT(*) FILTER (WHERE enrollment_year = 2025) AS student_count_25,
              COUNT(*) AS student_count_total
            FROM supervised_students
            WHERE COALESCE(home_university, '') ILIKE ('%' || $1 || '%')
            """,
            _normalize_text(institution_name),
        )

    return {
        "student_count_24": int((row or {}).get("student_count_24") or 0),
        "student_count_25": int((row or {}).get("student_count_25") or 0),
        "student_count_total": int((row or {}).get("student_count_total") or 0),
    }


async def get_institution_detail(institution_id: str) -> InstitutionDetailResponse | None:
    """Get detailed information for a single institution.

    Args:
        institution_id: Institution ID

    Returns:
        InstitutionDetailResponse or None if not found
    """
    # Fetch the institution
    record = await fetch_institution_by_id(institution_id)
    if not record:
        return None

    # If it's an organization, fetch its departments
    departments = None
    if record.get("entity_type") == "organization":
        all_records = await fetch_all_institutions()
        departments = [r for r in all_records if r.get("parent_id") == institution_id]

    metrics = await _load_student_metrics_for_institution(
        _normalize_text(record.get("name")),
        org_name=_normalize_text(record.get("org_name")) or None,
    )
    enriched_record = {
        **record,
        "student_count_24": metrics["student_count_24"],
        "student_count_25": metrics["student_count_25"],
        "student_count_total": metrics["student_count_total"],
    }

    # Build and return response
    return build_detail_response(enriched_record, departments)
