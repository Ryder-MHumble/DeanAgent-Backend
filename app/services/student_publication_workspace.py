from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg

from app.schemas.student import (
    StudentPaperRecord,
    StudentPublicationCandidateActionResponse,
    StudentPublicationCandidateDecisionRequest,
    StudentPublicationCandidatePatchRequest,
    StudentPublicationCandidateRecord,
    StudentPublicationWorkspaceCounts,
    StudentPublicationWorkspaceResponse,
)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _to_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    if isinstance(value, tuple):
        return [_clean_text(item) for item in value if _clean_text(item)]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            token = _clean_text(value)
            return [token] if token else []
        return _to_text_list(parsed)
    return []


def _to_json_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        token = _clean_text(value)
        if not token:
            return {}
        try:
            parsed = json.loads(token)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = _clean_text(value)
    return text or None


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = _to_iso(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _normalize_doi(value: Any) -> str | None:
    raw = _clean_text(value).lower()
    if not raw:
        return None
    raw = raw.replace("https://doi.org/", "").replace("http://doi.org/", "")
    raw = raw.replace("doi:", "").strip()
    return raw or None


def _normalize_arxiv_id(value: Any) -> str | None:
    raw = _clean_text(value).lower()
    if not raw:
        return None
    raw = raw.replace("https://arxiv.org/abs/", "").replace("http://arxiv.org/abs/", "")
    raw = raw.replace("arxiv:", "").replace("abs/", "").replace("pdf/", "").strip("/")
    return raw or None


def _title_fingerprint(title: Any) -> str:
    normalized = re.sub(
        r"\s+",
        " ",
        re.sub(r"[^\w\u4e00-\u9fff]+", " ", _clean_text(title).lower()),
    ).strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:20]


def _date_key(value: Any) -> str:
    resolved = _to_datetime(value)
    if resolved is None:
        return "0001-01-01"
    return resolved.date().isoformat()


def _build_canonical_uid(
    *,
    doi: Any = None,
    arxiv_id: Any = None,
    title: Any = None,
    publication_date: Any = None,
) -> str:
    doi_norm = _normalize_doi(doi)
    if doi_norm:
        return f"doi:{doi_norm}"
    arxiv_norm = _normalize_arxiv_id(arxiv_id)
    if arxiv_norm:
        return f"arxiv:{arxiv_norm}"
    digest = hashlib.sha1(
        f"{_title_fingerprint(title)}|{_date_key(publication_date)}".encode("utf-8")
    ).hexdigest()[:24]
    return f"fingerprint:{digest}"


def _build_dedup_metadata(
    *,
    paper_uid: Any,
    doi: Any,
    arxiv_id: Any,
    title: Any,
    publication_date: Any,
) -> tuple[str, str]:
    doi_norm = _normalize_doi(doi)
    arxiv_norm = _normalize_arxiv_id(arxiv_id)
    title_fp = _title_fingerprint(title)
    date_token = _date_key(publication_date)
    if doi_norm:
        return f"doi:{doi_norm}", title_fp
    if arxiv_norm:
        return f"arxiv:{arxiv_norm}", title_fp
    normalized_uid = _clean_text(paper_uid).lower()
    if normalized_uid.startswith("openalex:"):
        return normalized_uid, title_fp
    return f"title:{title_fp}|date:{date_token}", title_fp


def _to_student_paper(row: dict[str, Any]) -> StudentPaperRecord:
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


def _to_candidate_record(row: dict[str, Any]) -> StudentPublicationCandidateRecord:
    return StudentPublicationCandidateRecord(
        candidate_id=_clean_text(row.get("candidate_id")),
        target_key=_clean_text(row.get("target_key")) or None,
        owner_type=_clean_text(row.get("owner_type")),
        owner_id=_clean_text(row.get("owner_id")),
        canonical_uid=_clean_text(row.get("canonical_uid")),
        paper_uid=_clean_text(row.get("paper_uid")) or None,
        title=_clean_text(row.get("title")),
        doi=_clean_text(row.get("doi")) or None,
        arxiv_id=_clean_text(row.get("arxiv_id")) or None,
        abstract=_clean_text(row.get("abstract")) or None,
        publication_date=_to_iso(row.get("publication_date")),
        source=_clean_text(row.get("source")) or None,
        source_type=_clean_text(row.get("source_type")) or None,
        source_details=_to_json_dict(row.get("source_details")),
        authors=_to_text_list(row.get("authors")),
        affiliations=_to_text_list(row.get("affiliations")),
        review_status=_clean_text(row.get("review_status")) or "pending_review",
        review_decision=_to_json_dict(row.get("review_decision")),
        compliance_details=_to_json_dict(row.get("compliance_details")),
        affiliation_status=_clean_text(row.get("affiliation_status")) or None,
        compliance_reason=_clean_text(row.get("compliance_reason")) or None,
        matched_tokens=_to_text_list(row.get("matched_tokens")),
        checked_affiliations=_to_text_list(row.get("checked_affiliations")),
        assessed_at=_to_iso(row.get("assessed_at")),
        first_seen_at=_to_iso(row.get("first_seen_at")),
        last_seen_at=_to_iso(row.get("last_seen_at")),
        created_at=_to_iso(row.get("created_at")),
        updated_at=_to_iso(row.get("updated_at")),
    )


async def get_workspace(
    pool: asyncpg.Pool,
    *,
    student_id: str,
) -> StudentPublicationWorkspaceResponse:
    confirmed_rows = await pool.fetch(
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
        WHERE target_key = $1
        ORDER BY publication_date DESC NULLS LAST, created_at DESC, paper_uid ASC
        """,
        student_id,
    )
    candidate_rows = await pool.fetch(
        """
        SELECT
          candidate_id,
          target_key,
          owner_type,
          owner_id,
          canonical_uid,
          paper_uid,
          title,
          doi,
          arxiv_id,
          abstract,
          publication_date,
          authors,
          affiliations,
          source,
          source_type,
          source_details,
          review_status,
          review_decision,
          compliance_details,
          affiliation_status,
          compliance_reason,
          matched_tokens,
          checked_affiliations,
          assessed_at,
          first_seen_at,
          last_seen_at,
          created_at,
          updated_at
        FROM publication_candidates
        WHERE owner_type = 'student'
          AND owner_id = $1
        ORDER BY
          CASE review_status
            WHEN 'pending_review' THEN 0
            WHEN 'rejected' THEN 1
            ELSE 2
          END,
          last_seen_at DESC,
          created_at DESC,
          candidate_id ASC
        """,
        student_id,
    )

    pending_candidates: list[StudentPublicationCandidateRecord] = []
    rejected_candidates: list[StudentPublicationCandidateRecord] = []
    for row in candidate_rows:
        record = _to_candidate_record(dict(row))
        if record.review_status == "pending_review":
            pending_candidates.append(record)
        elif record.review_status == "rejected":
            rejected_candidates.append(record)

    confirmed_publications = [_to_student_paper(dict(row)) for row in confirmed_rows]
    return StudentPublicationWorkspaceResponse(
        counts=StudentPublicationWorkspaceCounts(
            confirmed=len(confirmed_publications),
            pending_review=len(pending_candidates),
            rejected=len(rejected_candidates),
        ),
        confirmed_publications=confirmed_publications,
        pending_candidates=pending_candidates,
        rejected_candidates=rejected_candidates,
    )


async def _load_candidate_for_update(
    conn: asyncpg.Connection,
    *,
    student_id: str,
    candidate_id: str,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT *
        FROM publication_candidates
        WHERE candidate_id = $1
          AND owner_type = 'student'
          AND owner_id = $2
        FOR UPDATE
        """,
        candidate_id,
        student_id,
    )


async def patch_candidate(
    pool: asyncpg.Pool,
    *,
    student_id: str,
    candidate_id: str,
    body: StudentPublicationCandidatePatchRequest,
) -> StudentPublicationCandidateRecord | None:
    async with pool.acquire() as conn, conn.transaction():
        current = await _load_candidate_for_update(
            conn,
            student_id=student_id,
            candidate_id=candidate_id,
        )
        if current is None:
            return None

        current_row = dict(current)
        title = (
            _clean_text(body.title)
            if body.title is not None
            else _clean_text(current_row.get("title"))
        )
        if not title:
            raise ValueError("candidate title cannot be empty")

        doi = _normalize_doi(body.doi) if body.doi is not None else _normalize_doi(current_row.get("doi"))
        arxiv_id = (
            _normalize_arxiv_id(body.arxiv_id)
            if body.arxiv_id is not None
            else _normalize_arxiv_id(current_row.get("arxiv_id"))
        )
        abstract = (
            _clean_text(body.abstract) or None
            if body.abstract is not None
            else (_clean_text(current_row.get("abstract")) or None)
        )
        publication_date = (
            _to_datetime(body.publication_date)
            if body.publication_date is not None
            else _to_datetime(current_row.get("publication_date"))
        )
        source = (
            _clean_text(body.source) or None
            if body.source is not None
            else (_clean_text(current_row.get("source")) or None)
        )
        authors = (
            _to_text_list(body.authors)
            if body.authors is not None
            else _to_text_list(current_row.get("authors"))
        )
        affiliations = (
            _to_text_list(body.affiliations)
            if body.affiliations is not None
            else _to_text_list(current_row.get("affiliations"))
        )
        canonical_uid = _build_canonical_uid(
            doi=doi,
            arxiv_id=arxiv_id,
            title=title,
            publication_date=publication_date,
        )
        dedup_key, title_fp = _build_dedup_metadata(
            paper_uid=current_row.get("paper_uid"),
            doi=doi,
            arxiv_id=arxiv_id,
            title=title,
            publication_date=publication_date,
        )
        conflict = await conn.fetchrow(
            """
            SELECT candidate_id
            FROM publication_candidates
            WHERE owner_type = 'student'
              AND owner_id = $1
              AND canonical_uid = $2
              AND candidate_id <> $3
            LIMIT 1
            """,
            student_id,
            canonical_uid,
            candidate_id,
        )
        if conflict is not None:
            raise ValueError("candidate canonical_uid conflicts with an existing candidate")

        updated = await conn.fetchrow(
            """
            UPDATE publication_candidates
            SET
              target_key = $3,
              canonical_uid = $4,
              title = $5,
              doi = $6,
              arxiv_id = $7,
              abstract = $8,
              publication_date = $9,
              source = $10,
              authors = $11::jsonb,
              affiliations = $12::jsonb,
              dedup_key = $13,
              title_fingerprint = $14,
              updated_at = now()
            WHERE candidate_id = $1
              AND owner_type = 'student'
              AND owner_id = $2
            RETURNING *
            """,
            candidate_id,
            student_id,
            student_id,
            canonical_uid,
            title,
            doi,
            arxiv_id,
            abstract,
            publication_date,
            source,
            json.dumps(authors),
            json.dumps(affiliations),
            dedup_key,
            title_fp,
        )
        assert updated is not None
        return _to_candidate_record(dict(updated))


def _merge_review_decision(
    current: dict[str, Any],
    *,
    action: str,
    reviewed_by: str | None,
    note: str | None,
    paper_uid: str | None = None,
) -> dict[str, Any]:
    merged = dict(current)
    merged.update(
        {
            "action": action,
            "reviewed_by": _clean_text(reviewed_by) or None,
            "note": _clean_text(note) or None,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    if paper_uid:
        merged["paper_uid"] = paper_uid
    return merged


def _merge_compliance_details(
    current: dict[str, Any],
    *,
    action: str,
    body: StudentPublicationCandidateDecisionRequest,
) -> dict[str, Any]:
    merged = dict(current)
    if body.compliance_details:
        merged.update(body.compliance_details)
    if body.affiliation_status is not None:
        merged["affiliation_status"] = _clean_text(body.affiliation_status) or None
    if body.compliance_reason is not None:
        merged["compliance_reason"] = _clean_text(body.compliance_reason) or None
    if body.matched_tokens is not None:
        merged["matched_tokens"] = _to_text_list(body.matched_tokens)
    if body.checked_affiliations is not None:
        merged["checked_affiliations"] = _to_text_list(body.checked_affiliations)
    merged["last_action"] = action
    merged["last_reviewed_at"] = datetime.now(timezone.utc).isoformat()
    if body.note is not None:
        merged["review_note"] = _clean_text(body.note) or None
    return merged


def _candidate_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": _clean_text(row.get("title")),
        "doi": _normalize_doi(row.get("doi")),
        "arxiv_id": _normalize_arxiv_id(row.get("arxiv_id")),
        "abstract": _clean_text(row.get("abstract")) or None,
        "publication_date": _to_datetime(row.get("publication_date")),
        "source": _clean_text(row.get("source")) or None,
        "authors": _to_text_list(row.get("authors")),
        "affiliations": _to_text_list(row.get("affiliations")),
    }


def _merge_confirmed_row(existing: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": candidate["title"] or _clean_text(existing.get("title")),
        "doi": candidate["doi"] or _normalize_doi(existing.get("doi")),
        "arxiv_id": candidate["arxiv_id"] or _normalize_arxiv_id(existing.get("arxiv_id")),
        "abstract": candidate["abstract"] or (_clean_text(existing.get("abstract")) or None),
        "publication_date": candidate["publication_date"] or _to_datetime(existing.get("publication_date")),
        "source": candidate["source"] or (_clean_text(existing.get("source")) or None),
        "authors": candidate["authors"] or _to_text_list(existing.get("authors")),
        "affiliations": candidate["affiliations"] or _to_text_list(existing.get("affiliations")),
    }


async def _find_existing_confirmed_publication(
    conn: asyncpg.Connection,
    *,
    student_id: str,
    canonical_uid: str,
) -> dict[str, Any] | None:
    rows = await conn.fetch(
        """
        SELECT
          target_key,
          paper_uid,
          title,
          doi,
          arxiv_id,
          abstract,
          publication_date,
          source,
          authors,
          affiliations,
          created_at,
          updated_at
        FROM student_publications
        WHERE target_key = $1
        """,
        student_id,
    )
    for row in rows:
        payload = dict(row)
        existing_uid = _build_canonical_uid(
            doi=payload.get("doi"),
            arxiv_id=payload.get("arxiv_id"),
            title=payload.get("title"),
            publication_date=payload.get("publication_date"),
        )
        if existing_uid == canonical_uid:
            return payload
    return None


async def confirm_candidate(
    pool: asyncpg.Pool,
    *,
    student_id: str,
    candidate_id: str,
    body: StudentPublicationCandidateDecisionRequest,
) -> StudentPublicationCandidateActionResponse | None:
    async with pool.acquire() as conn, conn.transaction():
        current = await _load_candidate_for_update(
            conn,
            student_id=student_id,
            candidate_id=candidate_id,
        )
        if current is None:
            return None

        current_row = dict(current)
        snapshot = _candidate_snapshot(current_row)
        canonical_uid = _build_canonical_uid(
            doi=snapshot["doi"],
            arxiv_id=snapshot["arxiv_id"],
            title=snapshot["title"],
            publication_date=snapshot["publication_date"],
        )
        existing_publication = await _find_existing_confirmed_publication(
            conn,
            student_id=student_id,
            canonical_uid=canonical_uid,
        )

        if existing_publication is None:
            paper_uid = f"paper_{uuid4().hex[:24]}"
            await conn.execute(
                """
                INSERT INTO student_publications (
                  target_key,
                  paper_uid,
                  title,
                  doi,
                  arxiv_id,
                  abstract,
                  publication_date,
                  source,
                  authors,
                  affiliations
                )
                VALUES (
                  $1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10::jsonb
                )
                """,
                student_id,
                paper_uid,
                snapshot["title"],
                snapshot["doi"],
                snapshot["arxiv_id"],
                snapshot["abstract"],
                snapshot["publication_date"],
                snapshot["source"] or "monitor_api",
                json.dumps(snapshot["authors"]),
                json.dumps(snapshot["affiliations"]),
            )
        else:
            paper_uid = _clean_text(existing_publication.get("paper_uid"))
            merged = _merge_confirmed_row(existing_publication, snapshot)
            await conn.execute(
                """
                UPDATE student_publications
                SET
                  title = $3,
                  doi = $4,
                  arxiv_id = $5,
                  abstract = $6,
                  publication_date = $7,
                  source = $8,
                  authors = $9::jsonb,
                  affiliations = $10::jsonb,
                  updated_at = now()
                WHERE target_key = $1
                  AND paper_uid = $2
                """,
                student_id,
                paper_uid,
                merged["title"],
                merged["doi"],
                merged["arxiv_id"],
                merged["abstract"],
                merged["publication_date"],
                merged["source"] or "monitor_api",
                json.dumps(merged["authors"]),
                json.dumps(merged["affiliations"]),
            )

        review_decision = _merge_review_decision(
            _to_json_dict(current_row.get("review_decision")),
            action="confirmed",
            reviewed_by=body.reviewed_by,
            note=body.note,
            paper_uid=paper_uid,
        )
        compliance_details = _merge_compliance_details(
            _to_json_dict(current_row.get("compliance_details")),
            action="confirmed",
            body=body,
        )
        await conn.execute(
            """
            UPDATE publication_candidates
            SET
              target_key = $3,
              canonical_uid = $4,
              review_status = 'confirmed',
              review_decision = $5::jsonb,
              compliance_details = $6::jsonb,
              affiliation_status = CASE WHEN $7::text IS NULL THEN affiliation_status ELSE $7 END,
              compliance_reason = CASE WHEN $8::text IS NULL THEN compliance_reason ELSE $8 END,
              matched_tokens = CASE WHEN $9::jsonb IS NULL THEN matched_tokens ELSE $9::jsonb END,
              checked_affiliations = CASE WHEN $10::jsonb IS NULL THEN checked_affiliations ELSE $10::jsonb END,
              assessed_at = now(),
              updated_at = now()
            WHERE candidate_id = $1
              AND owner_type = 'student'
              AND owner_id = $2
            """,
            candidate_id,
            student_id,
            student_id,
            canonical_uid,
            json.dumps(review_decision),
            json.dumps(compliance_details),
            _clean_text(body.affiliation_status) or None if body.affiliation_status is not None else None,
            _clean_text(body.compliance_reason) or None if body.compliance_reason is not None else None,
            json.dumps(_to_text_list(body.matched_tokens)) if body.matched_tokens is not None else None,
            json.dumps(_to_text_list(body.checked_affiliations)) if body.checked_affiliations is not None else None,
        )
        return StudentPublicationCandidateActionResponse(
            status="confirmed",
            candidate_id=candidate_id,
            paper_uid=paper_uid,
        )


async def reject_candidate(
    pool: asyncpg.Pool,
    *,
    student_id: str,
    candidate_id: str,
    body: StudentPublicationCandidateDecisionRequest,
) -> StudentPublicationCandidateActionResponse | None:
    async with pool.acquire() as conn, conn.transaction():
        current = await _load_candidate_for_update(
            conn,
            student_id=student_id,
            candidate_id=candidate_id,
        )
        if current is None:
            return None
        current_row = dict(current)
        review_decision = _merge_review_decision(
            _to_json_dict(current_row.get("review_decision")),
            action="rejected",
            reviewed_by=body.reviewed_by,
            note=body.note,
        )
        compliance_details = _merge_compliance_details(
            _to_json_dict(current_row.get("compliance_details")),
            action="rejected",
            body=body,
        )
        await conn.execute(
            """
            UPDATE publication_candidates
            SET
              target_key = $3,
              review_status = 'rejected',
              review_decision = $4::jsonb,
              compliance_details = $5::jsonb,
              affiliation_status = CASE WHEN $6::text IS NULL THEN affiliation_status ELSE $6 END,
              compliance_reason = CASE WHEN $7::text IS NULL THEN compliance_reason ELSE $7 END,
              matched_tokens = CASE WHEN $8::jsonb IS NULL THEN matched_tokens ELSE $8::jsonb END,
              checked_affiliations = CASE WHEN $9::jsonb IS NULL THEN checked_affiliations ELSE $9::jsonb END,
              assessed_at = now(),
              updated_at = now()
            WHERE candidate_id = $1
              AND owner_type = 'student'
              AND owner_id = $2
            """,
            candidate_id,
            student_id,
            student_id,
            json.dumps(review_decision),
            json.dumps(compliance_details),
            _clean_text(body.affiliation_status) or None if body.affiliation_status is not None else None,
            _clean_text(body.compliance_reason) or None if body.compliance_reason is not None else None,
            json.dumps(_to_text_list(body.matched_tokens)) if body.matched_tokens is not None else None,
            json.dumps(_to_text_list(body.checked_affiliations)) if body.checked_affiliations is not None else None,
        )
        return StudentPublicationCandidateActionResponse(
            status="rejected",
            candidate_id=candidate_id,
        )


async def reopen_candidate(
    pool: asyncpg.Pool,
    *,
    student_id: str,
    candidate_id: str,
    body: StudentPublicationCandidateDecisionRequest,
) -> StudentPublicationCandidateActionResponse | None:
    async with pool.acquire() as conn, conn.transaction():
        current = await _load_candidate_for_update(
            conn,
            student_id=student_id,
            candidate_id=candidate_id,
        )
        if current is None:
            return None
        current_row = dict(current)
        review_decision = _merge_review_decision(
            _to_json_dict(current_row.get("review_decision")),
            action="reopened",
            reviewed_by=body.reviewed_by,
            note=body.note,
        )
        compliance_details = _merge_compliance_details(
            _to_json_dict(current_row.get("compliance_details")),
            action="reopened",
            body=body,
        )
        await conn.execute(
            """
            UPDATE publication_candidates
            SET
              target_key = $3,
              review_status = 'pending_review',
              review_decision = $4::jsonb,
              compliance_details = $5::jsonb,
              affiliation_status = CASE WHEN $6::text IS NULL THEN affiliation_status ELSE $6 END,
              compliance_reason = CASE WHEN $7::text IS NULL THEN compliance_reason ELSE $7 END,
              matched_tokens = CASE WHEN $8::jsonb IS NULL THEN matched_tokens ELSE $8::jsonb END,
              checked_affiliations = CASE WHEN $9::jsonb IS NULL THEN checked_affiliations ELSE $9::jsonb END,
              assessed_at = now(),
              updated_at = now()
            WHERE candidate_id = $1
              AND owner_type = 'student'
              AND owner_id = $2
            """,
            candidate_id,
            student_id,
            student_id,
            json.dumps(review_decision),
            json.dumps(compliance_details),
            _clean_text(body.affiliation_status) or None if body.affiliation_status is not None else None,
            _clean_text(body.compliance_reason) or None if body.compliance_reason is not None else None,
            json.dumps(_to_text_list(body.matched_tokens)) if body.matched_tokens is not None else None,
            json.dumps(_to_text_list(body.checked_affiliations)) if body.checked_affiliations is not None else None,
        )
        return StudentPublicationCandidateActionResponse(
            status="pending_review",
            candidate_id=candidate_id,
        )
