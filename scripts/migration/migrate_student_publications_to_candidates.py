#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "migration" / "reports"


def _load_repo_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_name(value: str) -> str:
    return (
        _clean_text(value)
        .lower()
        .replace(" ", "")
        .replace("\u3000", "")
        .replace("·", "")
        .replace("•", "")
    )


def _stable_student_target_key_from_name(name: str) -> str:
    normalized = f"student|{_clean_text(name).lower()}"
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:20]
    return f"student_{digest}"


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


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = _clean_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _date_key(value: Any) -> str:
    resolved = _to_datetime(value)
    if resolved is None:
        return "0001-01-01"
    return resolved.date().isoformat()


def _build_canonical_uid(
    *,
    doi: Any,
    arxiv_id: Any,
    title: Any,
    publication_date: Any,
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


def _build_candidate_id(owner_type: str, owner_id: str, canonical_uid: str) -> str:
    digest = hashlib.sha1(
        f"{owner_type}|{owner_id}|{canonical_uid}".encode("utf-8")
    ).hexdigest()[:24]
    return f"candidate_{digest}"


def _merge_unique_text(existing: list[str], incoming: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in existing + incoming:
        token = _clean_text(value)
        if not token or token in seen:
            continue
        merged.append(token)
        seen.add(token)
    return merged


def _to_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    if isinstance(value, tuple):
        return [_clean_text(item) for item in value if _clean_text(item)]
    if isinstance(value, str):
        token = _clean_text(value)
        if not token:
            return []
        try:
            parsed = json.loads(token)
        except json.JSONDecodeError:
            return [token]
        return _to_text_list(parsed)
    return []


@dataclass
class CandidateAggregate:
    owner_id: str
    canonical_uid: str
    title: str
    doi: str | None
    arxiv_id: str | None
    abstract: str | None
    publication_date: datetime | None
    source: str | None
    authors: list[str]
    affiliations: list[str]
    paper_uid: str | None
    source_rows: list[dict[str, Any]] = field(default_factory=list)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


def _prefer_text(current: str | None, incoming: str | None, *, prefer_longer: bool = False) -> str | None:
    current_token = _clean_text(current) or None
    incoming_token = _clean_text(incoming) or None
    if current_token is None:
        return incoming_token
    if incoming_token is None:
        return current_token
    if prefer_longer and len(incoming_token) > len(current_token):
        return incoming_token
    return current_token


def _snapshot_row(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "target_key": _clean_text(row["target_key"]),
        "paper_uid": _clean_text(row["paper_uid"]),
        "title": _clean_text(row["title"]),
        "doi": _normalize_doi(row["doi"]),
        "arxiv_id": _normalize_arxiv_id(row["arxiv_id"]),
        "abstract": _clean_text(row["abstract"]) or None,
        "publication_date": row["publication_date"].isoformat() if row["publication_date"] else None,
        "source": _clean_text(row["source"]) or None,
        "authors": _to_text_list(row["authors"]),
        "affiliations": _to_text_list(row["affiliations"]),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def _merge_candidate(existing: CandidateAggregate | None, row: asyncpg.Record, *, owner_id: str, canonical_uid: str) -> CandidateAggregate:
    row_title = _clean_text(row["title"])
    row_doi = _normalize_doi(row["doi"])
    row_arxiv = _normalize_arxiv_id(row["arxiv_id"])
    row_abstract = _clean_text(row["abstract"]) or None
    row_publication_date = _to_datetime(row["publication_date"])
    row_source = _clean_text(row["source"]) or None
    row_authors = _to_text_list(row["authors"])
    row_affiliations = _to_text_list(row["affiliations"])
    row_created_at = _to_datetime(row["created_at"])
    row_updated_at = _to_datetime(row["updated_at"])
    if existing is None:
        return CandidateAggregate(
            owner_id=owner_id,
            canonical_uid=canonical_uid,
            title=row_title,
            doi=row_doi,
            arxiv_id=row_arxiv,
            abstract=row_abstract,
            publication_date=row_publication_date,
            source=row_source,
            authors=row_authors,
            affiliations=row_affiliations,
            paper_uid=_clean_text(row["paper_uid"]) or None,
            source_rows=[_snapshot_row(row)],
            first_seen_at=row_created_at or row_updated_at,
            last_seen_at=row_updated_at or row_created_at,
            created_at=row_created_at,
            updated_at=row_updated_at,
        )

    existing.title = _prefer_text(existing.title, row_title) or row_title
    existing.doi = _prefer_text(existing.doi, row_doi)
    existing.arxiv_id = _prefer_text(existing.arxiv_id, row_arxiv)
    existing.abstract = _prefer_text(existing.abstract, row_abstract, prefer_longer=True)
    existing.publication_date = existing.publication_date or row_publication_date
    existing.source = _prefer_text(existing.source, row_source)
    existing.authors = _merge_unique_text(existing.authors, row_authors)
    existing.affiliations = _merge_unique_text(existing.affiliations, row_affiliations)
    existing.paper_uid = existing.paper_uid or (_clean_text(row["paper_uid"]) or None)
    existing.source_rows.append(_snapshot_row(row))
    if row_created_at and (existing.first_seen_at is None or row_created_at < existing.first_seen_at):
        existing.first_seen_at = row_created_at
    if row_updated_at and (existing.last_seen_at is None or row_updated_at > existing.last_seen_at):
        existing.last_seen_at = row_updated_at
    if row_created_at and (existing.created_at is None or row_created_at < existing.created_at):
        existing.created_at = row_created_at
    if row_updated_at and (existing.updated_at is None or row_updated_at > existing.updated_at):
        existing.updated_at = row_updated_at
    return existing


async def _connect_from_env() -> asyncpg.Connection:
    _load_repo_env()
    dsn = _clean_text(os.getenv("POSTGRES_DSN"))
    if dsn:
        return await asyncpg.connect(dsn=dsn)
    return await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        database=os.getenv("POSTGRES_DB", "postgres"),
    )


async def migrate(*, dry_run: bool) -> dict[str, Any]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = await _connect_from_env()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_student_table = f"student_publications_backup_{stamp}"
    backup_candidate_table = f"publication_candidates_backup_{stamp}"
    report_path = REPORT_DIR / f"student_publications_migration_{stamp}.json"
    migrated_at = datetime.now(timezone.utc).isoformat()

    try:
        student_rows = await conn.fetch(
            """
            SELECT id, name
            FROM supervised_students
            WHERE COALESCE(name, '') <> ''
            """
        )
        student_ids = {_clean_text(row["id"]) for row in student_rows if _clean_text(row["id"])}
        name_key_map: dict[str, str | None] = {}
        for row in student_rows:
            student_id = _clean_text(row["id"])
            if not student_id:
                continue
            name_key = _stable_student_target_key_from_name(_clean_text(row["name"]))
            if not name_key:
                continue
            if name_key in name_key_map and name_key_map[name_key] != student_id:
                name_key_map[name_key] = None
            else:
                name_key_map[name_key] = student_id

        source_rows = await conn.fetch(
            """
            SELECT
              target_key,
              paper_uid,
              title,
              doi,
              arxiv_id,
              abstract,
              publication_date,
              authors,
              affiliations,
              source,
              created_at,
              updated_at
            FROM student_publications
            ORDER BY created_at ASC, updated_at ASC, target_key ASC, paper_uid ASC
            """
        )

        aggregates: dict[tuple[str, str], CandidateAggregate] = {}
        unmatched_rows: list[dict[str, Any]] = []
        matched_row_count = 0

        for row in source_rows:
            target_key = _clean_text(row["target_key"])
            resolved_student_id: str | None = None
            matched_by = ""
            if target_key in student_ids:
                resolved_student_id = target_key
                matched_by = "student_id"
            else:
                resolved_student_id = name_key_map.get(target_key)
                if resolved_student_id:
                    matched_by = "normalized_name_key"

            if not resolved_student_id:
                unmatched_rows.append(
                    {
                        "reason": "student_not_matched",
                        "target_key": target_key,
                        "paper_uid": _clean_text(row["paper_uid"]),
                        "title": _clean_text(row["title"]),
                        "doi": _normalize_doi(row["doi"]),
                        "arxiv_id": _normalize_arxiv_id(row["arxiv_id"]),
                    }
                )
                continue

            matched_row_count += 1
            canonical_uid = _build_canonical_uid(
                doi=row["doi"],
                arxiv_id=row["arxiv_id"],
                title=row["title"],
                publication_date=row["publication_date"],
            )
            key = (resolved_student_id, canonical_uid)
            aggregate = _merge_candidate(
                aggregates.get(key),
                row,
                owner_id=resolved_student_id,
                canonical_uid=canonical_uid,
            )
            aggregate.source_rows[-1]["matched_by"] = matched_by
            aggregates[key] = aggregate

        if not dry_run:
            async with conn.transaction():
                await conn.execute(
                    f'CREATE TABLE "{backup_student_table}" AS TABLE student_publications'
                )
                await conn.execute(
                    f'CREATE TABLE "{backup_candidate_table}" AS TABLE publication_candidates'
                )
                for aggregate in aggregates.values():
                    dedup_key, title_fp = _build_dedup_metadata(
                        paper_uid=aggregate.paper_uid,
                        doi=aggregate.doi,
                        arxiv_id=aggregate.arxiv_id,
                        title=aggregate.title,
                        publication_date=aggregate.publication_date,
                    )
                    source_details = {
                        "migration": "student_publications_to_publication_candidates",
                        "migrated_at": migrated_at,
                        "legacy_row_count": len(aggregate.source_rows),
                        "legacy_rows": aggregate.source_rows,
                    }
                    review_decision = {
                        "migration_status": "pending_review",
                        "migrated_at": migrated_at,
                        "migrated_from": "student_publications",
                    }
                    await conn.execute(
                        """
                        INSERT INTO publication_candidates (
                          candidate_id,
                          owner_type,
                          owner_id,
                          target_key,
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
                          first_seen_at,
                          last_seen_at,
                          created_at,
                          updated_at,
                          dedup_key,
                          title_fingerprint
                        )
                        VALUES (
                          $1, 'student', $2, $3, $4, $5, $6, $7, $8, $9, $10,
                          $11::jsonb, $12::jsonb, $13, 'legacy_migrated', $14::jsonb,
                          'pending_review', $15::jsonb, $16, $17, $18, $19, $20, $21
                        )
                        ON CONFLICT (owner_type, owner_id, canonical_uid) DO UPDATE
                        SET
                          target_key = EXCLUDED.target_key,
                          paper_uid = COALESCE(publication_candidates.paper_uid, EXCLUDED.paper_uid),
                          title = CASE
                            WHEN COALESCE(publication_candidates.title, '') = '' THEN EXCLUDED.title
                            ELSE publication_candidates.title
                          END,
                          doi = COALESCE(publication_candidates.doi, EXCLUDED.doi),
                          arxiv_id = COALESCE(publication_candidates.arxiv_id, EXCLUDED.arxiv_id),
                          abstract = COALESCE(publication_candidates.abstract, EXCLUDED.abstract),
                          publication_date = COALESCE(publication_candidates.publication_date, EXCLUDED.publication_date),
                          authors = CASE
                            WHEN publication_candidates.authors = '[]'::jsonb THEN EXCLUDED.authors
                            ELSE publication_candidates.authors
                          END,
                          affiliations = CASE
                            WHEN publication_candidates.affiliations = '[]'::jsonb THEN EXCLUDED.affiliations
                            ELSE publication_candidates.affiliations
                          END,
                          source = COALESCE(publication_candidates.source, EXCLUDED.source),
                          source_details = publication_candidates.source_details || EXCLUDED.source_details,
                          first_seen_at = LEAST(publication_candidates.first_seen_at, EXCLUDED.first_seen_at),
                          last_seen_at = GREATEST(publication_candidates.last_seen_at, EXCLUDED.last_seen_at),
                          created_at = LEAST(publication_candidates.created_at, EXCLUDED.created_at),
                          updated_at = GREATEST(publication_candidates.updated_at, EXCLUDED.updated_at),
                          dedup_key = COALESCE(publication_candidates.dedup_key, EXCLUDED.dedup_key),
                          title_fingerprint = COALESCE(publication_candidates.title_fingerprint, EXCLUDED.title_fingerprint)
                        """,
                        _build_candidate_id("student", aggregate.owner_id, aggregate.canonical_uid),
                        aggregate.owner_id,
                        aggregate.owner_id,
                        aggregate.canonical_uid,
                        aggregate.paper_uid,
                        aggregate.title,
                        aggregate.doi,
                        aggregate.arxiv_id,
                        aggregate.abstract,
                        aggregate.publication_date,
                        json.dumps(aggregate.authors),
                        json.dumps(aggregate.affiliations),
                        aggregate.source or "legacy_migrated",
                        json.dumps(source_details),
                        json.dumps(review_decision),
                        aggregate.first_seen_at or aggregate.created_at or aggregate.updated_at or datetime.now(timezone.utc),
                        aggregate.last_seen_at or aggregate.updated_at or aggregate.created_at or datetime.now(timezone.utc),
                        aggregate.created_at or aggregate.first_seen_at or datetime.now(timezone.utc),
                        aggregate.updated_at or aggregate.last_seen_at or datetime.now(timezone.utc),
                        dedup_key,
                        title_fp,
                    )
                await conn.execute("TRUNCATE TABLE student_publications")

        report = {
            "generated_at": migrated_at,
            "dry_run": dry_run,
            "backup_student_publications_table": None if dry_run else backup_student_table,
            "backup_publication_candidates_table": None if dry_run else backup_candidate_table,
            "source_row_count": len(source_rows),
            "matched_source_rows": matched_row_count,
            "candidate_upsert_count": len(aggregates),
            "unmatched_row_count": len(unmatched_rows),
            "unmatched_rows": unmatched_rows,
        }
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report["report_path"] = str(report_path)
        return report
    finally:
        await conn.close()


async def _async_main(args: argparse.Namespace) -> int:
    report = await migrate(dry_run=args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate legacy student_publications into publication_candidates."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the migration and generate the report without mutating the database.",
    )
    args = parser.parse_args()
    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
