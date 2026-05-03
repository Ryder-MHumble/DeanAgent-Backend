"""Compatibility APIs for academic-monitor student paper workflows.

These endpoints are mounted under `/academic-monitor/api` and the legacy
`/academic-monitor/api/v1` prefix so the
Scholars-System frontend can rely on this backend only.
"""
from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.pool import get_pool
from app.services import publication_service

router = APIRouter()


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = _clean_text(value)
    return text or None


def _to_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    if isinstance(value, tuple):
        return [_clean_text(item) for item in value if _clean_text(item)]
    if isinstance(value, str):
        token = _clean_text(value)
        return [token] if token else []
    return []


def _stable_student_target_key_from_name(name: str) -> str:
    normalized = f"student|{name.strip().lower()}"
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:20]
    return f"student_{digest}"


async def _student_publication_target_candidates(student_id: str) -> list[str]:
    normalized_student_id = _clean_text(student_id)
    if not normalized_student_id:
        return []

    candidates: list[str] = [normalized_student_id]
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT name
        FROM supervised_students
        WHERE id = $1
        LIMIT 1
        """,
        normalized_student_id,
    )
    if row:
        name = _clean_text(row["name"])
        if name:
            name_key = _stable_student_target_key_from_name(name)
            if name_key not in candidates:
                candidates.append(name_key)
    return candidates


async def _resolve_write_target_key(student_id: str) -> str:
    candidates = await _student_publication_target_candidates(student_id)
    if not candidates:
        return _clean_text(student_id)

    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT target_key, COUNT(*)::int AS cnt
        FROM student_publications
        WHERE target_key = ANY($1::text[])
        GROUP BY target_key
        """,
        candidates,
    )
    counts = {_clean_text(row["target_key"]): int(row["cnt"] or 0) for row in rows}
    for key in candidates:
        if counts.get(key, 0) > 0:
            return key
    return candidates[0]


async def _resolve_target_key_for_paper(student_id: str, paper_uid: str) -> str | None:
    candidates = await _student_publication_target_candidates(student_id)
    if not candidates:
        return None

    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT sp.target_key
        FROM student_publications sp
        JOIN unnest($1::text[]) WITH ORDINALITY AS c(target_key, ord)
          ON c.target_key = sp.target_key
        WHERE sp.paper_uid = $2
        ORDER BY c.ord ASC
        LIMIT 1
        """,
        candidates,
        _clean_text(paper_uid),
    )
    if not row:
        return None
    return _clean_text(row["target_key"])


class AcademicStudentSummary(BaseModel):
    target_key: str
    name: str
    target_type: str = "student"
    paper_count: int = 0
    compliant_count: int = 0
    non_compliant_count: int = 0
    unknown_count: int = 0


class AcademicStudentsResponse(BaseModel):
    items: list[AcademicStudentSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class StudentPaperRecord(BaseModel):
    paper_uid: str
    title: str
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    publication_date: str | None = None
    source: str | None = None
    authors: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    created_at: str | None = None


class AcademicStudentPapersResponse(BaseModel):
    items: list[StudentPaperRecord]
    total: int


class AcademicPaperUpsertPayload(BaseModel):
    title: str
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    publication_date: str | None = None
    source: str | None = None
    authors: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)


class AcademicPaperCompliancePayload(BaseModel):
    note: str | None = None


class PaperWriteResponse(BaseModel):
    status: str
    paper_uid: str


def _build_paper_record(row: dict[str, Any]) -> StudentPaperRecord:
    return StudentPaperRecord(
        paper_uid=_clean_text(row.get("paper_uid")),
        title=_clean_text(row.get("title")),
        doi=_clean_text(row.get("doi")) or None,
        arxiv_id=_clean_text(row.get("arxiv_id")) or None,
        abstract=_clean_text(row.get("abstract")) or None,
        publication_date=_to_iso(row.get("publication_date")),
        source=_clean_text(row.get("source")) or None,
        authors=_to_text_list(row.get("authors")),
        affiliations=_to_text_list(row.get("affiliations")),
        created_at=_to_iso(row.get("created_at")),
    )


def _build_formal_paper_record(row: dict[str, Any]) -> StudentPaperRecord:
    return StudentPaperRecord(
        paper_uid=_clean_text(row.get("owner_link_id")) or _clean_text(row.get("publication_id")),
        title=_clean_text(row.get("title")),
        doi=_clean_text(row.get("doi")) or None,
        arxiv_id=_clean_text(row.get("arxiv_id")) or None,
        abstract=_clean_text(row.get("abstract")) or None,
        publication_date=_to_iso(row.get("publication_date")),
        source=_clean_text(row.get("source")) or None,
        authors=_to_text_list(row.get("authors")),
        affiliations=_to_text_list(row.get("affiliations")),
        created_at=_to_iso(row.get("created_at")),
    )


@router.get(
    "/students",
    response_model=AcademicStudentsResponse,
    summary="academic-monitor 兼容：学生目标列表",
)
async def list_academic_students(
    keyword: str | None = Query(None, description="按学生姓名或 target_key 模糊匹配"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
) -> AcademicStudentsResponse:
    pool = get_pool()
    token = _clean_text(keyword)
    pattern = f"%{token}%"
    offset = (page - 1) * page_size

    total = int(
        await pool.fetchval(
            """
            SELECT COUNT(*)::bigint
            FROM supervised_students s
            WHERE ($1 = '' OR COALESCE(s.name, '') ILIKE $2 OR s.id ILIKE $2)
            """,
            token,
            pattern,
        )
        or 0
    )

    rows = await pool.fetch(
        """
        SELECT
          s.id AS target_key,
          s.name,
          s.updated_at,
          s.created_at
        FROM supervised_students s
        WHERE ($1 = '' OR COALESCE(s.name, '') ILIKE $2 OR s.id ILIKE $2)
        ORDER BY s.updated_at DESC NULLS LAST, s.created_at DESC, s.id ASC
        LIMIT $3 OFFSET $4
        """,
        token,
        pattern,
        page_size,
        offset,
    )

    stats_by_target: dict[str, dict[str, int]] = {}
    publication_keys: list[str] = []
    publication_key_owner: dict[str, str] = {}
    for row in rows:
        target_key = _clean_text(row["target_key"])
        name = _clean_text(row["name"])
        keys = [target_key]
        if name:
            name_key = _stable_student_target_key_from_name(name)
            if name_key not in keys:
                keys.append(name_key)
        for key in keys:
            publication_keys.append(key)
            publication_key_owner[key] = target_key

    if publication_keys:
        stat_rows = await pool.fetch(
            """
            SELECT
              target_key,
              COUNT(*)::int AS paper_count,
              0::int AS compliant_count,
              0::int AS non_compliant_count,
              COUNT(*)::int AS unknown_count
            FROM student_publications
            WHERE target_key = ANY($1::text[])
            GROUP BY target_key
            """,
            publication_keys,
        )
        for row in stat_rows:
            publication_key = _clean_text(row["target_key"])
            owner_key = publication_key_owner.get(publication_key)
            if not owner_key:
                continue
            current = stats_by_target.setdefault(
                owner_key,
                {
                    "paper_count": 0,
                    "compliant_count": 0,
                    "non_compliant_count": 0,
                    "unknown_count": 0,
                },
            )
            current["paper_count"] += int(row["paper_count"] or 0)
            current["compliant_count"] += int(row["compliant_count"] or 0)
            current["non_compliant_count"] += int(row["non_compliant_count"] or 0)
            current["unknown_count"] += int(row["unknown_count"] or 0)

    items = [
        AcademicStudentSummary(
            target_key=_clean_text(row["target_key"]),
            name=_clean_text(row["name"]),
            paper_count=stats_by_target.get(_clean_text(row["target_key"]), {}).get("paper_count", 0),
            compliant_count=stats_by_target.get(_clean_text(row["target_key"]), {}).get("compliant_count", 0),
            non_compliant_count=stats_by_target.get(_clean_text(row["target_key"]), {}).get("non_compliant_count", 0),
            unknown_count=stats_by_target.get(_clean_text(row["target_key"]), {}).get("unknown_count", 0),
        )
        for row in rows
    ]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return AcademicStudentsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/students/{target_key}/papers",
    response_model=AcademicStudentPapersResponse,
    summary="academic-monitor 兼容：学生论文列表",
)
async def list_academic_student_papers(target_key: str) -> AcademicStudentPapersResponse:
    pool = get_pool()
    formal_items = await publication_service.list_publications(
        pool,
        owner_type="student",
        owner_id=_clean_text(target_key),
    )
    if formal_items:
        records = [_build_formal_paper_record(item) for item in formal_items]
        return AcademicStudentPapersResponse(items=records, total=len(records))

    target_keys = await _student_publication_target_candidates(target_key)
    if not target_keys:
        return AcademicStudentPapersResponse(items=[], total=0)
    rows = await pool.fetch(
        """
        SELECT
          paper_uid,
          title,
          doi,
          arxiv_id,
          abstract,
          publication_date,
          source,
          authors,
          affiliations,
          created_at
        FROM student_publications
        WHERE target_key = ANY($1::text[])
        ORDER BY publication_date DESC NULLS LAST, created_at DESC, paper_uid ASC
        """,
        target_keys,
    )
    records = [_build_paper_record(dict(row)) for row in rows]
    return AcademicStudentPapersResponse(items=records, total=len(records))


@router.post(
    "/students/{target_key}/papers",
    response_model=PaperWriteResponse,
    summary="academic-monitor 兼容：新增学生论文",
)
async def create_academic_paper(
    target_key: str,
    payload: AcademicPaperUpsertPayload,
) -> PaperWriteResponse:
    result = await publication_service.create_formal_publication(
        get_pool(),
        owner_type="student",
        owner_id=_clean_text(target_key),
        title=_clean_text(payload.title),
        doi=_clean_text(payload.doi) or None,
        arxiv_id=_clean_text(payload.arxiv_id) or None,
        abstract=_clean_text(payload.abstract) or None,
        publication_date=payload.publication_date or None,
        authors=payload.authors,
        affiliations=payload.affiliations,
        source_type=_clean_text(payload.source) or "manual",
    )
    return PaperWriteResponse(
        status=result["status"],
        paper_uid=_clean_text(result.get("owner_link_id")) or _clean_text(result.get("publication_id")),
    )


@router.put(
    "/students/{target_key}/papers/{paper_uid}",
    response_model=PaperWriteResponse,
    summary="academic-monitor 兼容：更新学生论文",
)
async def update_academic_paper(
    target_key: str,
    paper_uid: str,
    payload: AcademicPaperUpsertPayload,
) -> PaperWriteResponse:
    pool = get_pool()
    resolved_target_key = await _resolve_target_key_for_paper(target_key, paper_uid)
    if not resolved_target_key:
        raise HTTPException(status_code=404, detail="paper not found")
    updated = await pool.fetchrow(
        """
        UPDATE student_publications
        SET
          title = $3,
          doi = $4,
          arxiv_id = $5,
          abstract = $6,
          publication_date = $7::timestamptz,
          source = $8,
          authors = $9::jsonb,
          affiliations = $10::jsonb,
          updated_at = now()
        WHERE target_key = $1 AND paper_uid = $2
        RETURNING paper_uid
        """,
        resolved_target_key,
        _clean_text(paper_uid),
        _clean_text(payload.title),
        _clean_text(payload.doi) or None,
        _clean_text(payload.arxiv_id) or None,
        _clean_text(payload.abstract) or None,
        payload.publication_date or None,
        _clean_text(payload.source) or "manual",
        payload.authors,
        payload.affiliations,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="paper not found")
    return PaperWriteResponse(status="updated", paper_uid=_clean_text(updated["paper_uid"]))


@router.patch(
    "/students/{target_key}/papers/{paper_uid}/compliance",
    response_model=PaperWriteResponse,
    summary="academic-monitor 兼容：更新论文（不再存储合规字段）",
)
async def patch_academic_paper_compliance(
    target_key: str,
    paper_uid: str,
    payload: AcademicPaperCompliancePayload,
) -> PaperWriteResponse:
    pool = get_pool()
    resolved_target_key = await _resolve_target_key_for_paper(target_key, paper_uid)
    if not resolved_target_key:
        raise HTTPException(status_code=404, detail="paper not found")
    updated = await pool.fetchrow(
        """
        UPDATE student_publications
        SET
          updated_at = now()
        WHERE target_key = $1 AND paper_uid = $2
        RETURNING paper_uid
        """,
        resolved_target_key,
        _clean_text(paper_uid),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="paper not found")
    return PaperWriteResponse(status="updated", paper_uid=_clean_text(updated["paper_uid"]))


@router.delete(
    "/students/{target_key}/papers/{paper_uid}",
    status_code=204,
    summary="academic-monitor 兼容：删除论文",
)
async def delete_academic_paper(target_key: str, paper_uid: str) -> None:
    pool = get_pool()
    resolved_target_key = await _resolve_target_key_for_paper(target_key, paper_uid)
    if not resolved_target_key:
        raise HTTPException(status_code=404, detail="paper not found")
    result = await pool.execute(
        """
        DELETE FROM student_publications
        WHERE target_key = $1 AND paper_uid = $2
        """,
        resolved_target_key,
        _clean_text(paper_uid),
    )
    if result.endswith("0"):
        raise HTTPException(status_code=404, detail="paper not found")
