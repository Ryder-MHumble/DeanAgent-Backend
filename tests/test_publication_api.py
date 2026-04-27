from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import academic_monitor
from app.api.v1 import publications, students
from app.config import settings
from app.db.pool import close_pool, get_pool, init_pool


def _build_test_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await close_pool()
        await init_pool(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
        )
        try:
            yield
        finally:
            await close_pool()

    app = FastAPI(lifespan=lifespan)
    app.include_router(publications.router, prefix="/api/v1")
    app.include_router(students.router, prefix="/api/v1/students")
    app.include_router(academic_monitor.router, prefix="/academic-monitor/api/v1")
    return app


@pytest.fixture()
def api_client():
    with TestClient(_build_test_app(), raise_server_exceptions=False) as client:
        yield client


async def _cleanup_publication_test_rows(prefix: str) -> None:
    pool = get_pool()
    publication_owners_exists = await pool.fetchval(
        "SELECT to_regclass('public.publication_owners') IS NOT NULL"
    )
    publications_exists = await pool.fetchval(
        "SELECT to_regclass('public.publications') IS NOT NULL"
    )
    await pool.execute(
        """
        DELETE FROM publication_candidates
        WHERE owner_id LIKE $1 OR candidate_id LIKE $1
        """,
        f"{prefix}%",
    )
    if publication_owners_exists:
        await pool.execute(
            """
            DELETE FROM publication_owners
            WHERE owner_id LIKE $1 OR owner_link_id LIKE $1
            """,
            f"{prefix}%",
        )
    if publications_exists:
        await pool.execute(
            """
            DELETE FROM publications
            WHERE publication_id LIKE $1 OR canonical_uid LIKE $1
            """,
            f"{prefix}%",
        )
    await pool.execute(
        """
        DELETE FROM supervised_students
        WHERE id LIKE $1
        """,
        f"{prefix}%",
    )
    await pool.execute(
        """
        DELETE FROM scholars
        WHERE id LIKE $1
        """,
        f"{prefix}%",
    )


async def _seed_student(prefix: str) -> tuple[str, str]:
    pool = get_pool()
    scholar_id = f"{prefix}_scholar"
    student_id = f"{prefix}_student"
    await pool.execute(
        """
        INSERT INTO scholars (id, name, updated_at)
        VALUES ($1, $2, now())
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name,
            updated_at = now()
        """,
        scholar_id,
        f"{prefix} Scholar",
    )
    await pool.execute(
        """
        INSERT INTO supervised_students (id, scholar_id, name, added_by, updated_at)
        VALUES ($1, $2, $3, 'user:test', now())
        ON CONFLICT (id) DO UPDATE
        SET scholar_id = EXCLUDED.scholar_id,
            name = EXCLUDED.name,
            updated_at = now()
        """,
        student_id,
        scholar_id,
        f"{prefix} Student",
    )
    return scholar_id, student_id


@pytest.mark.asyncio
async def test_manual_publication_enters_formal_layer_and_compat_student_api_reads_it(api_client: TestClient):
    prefix = f"test_pub_{uuid4().hex[:10]}"
    await _cleanup_publication_test_rows(prefix)
    _, student_id = await _seed_student(prefix)

    response = api_client.post(
        f"/academic-monitor/api/v1/students/{student_id}/papers",
        json={
            "title": f"{prefix} Manual Paper",
            "doi": f"{prefix}/manual-doi",
            "abstract": "manual paper abstract",
            "authors": ["Alice", "Bob"],
            "affiliations": ["Example University"],
            "source": "manual",
            "affiliation_status": "compliant",
            "compliance_reason": "manual check",
        },
    )

    assert response.status_code in {200, 201}, response.text
    payload = response.json()
    assert payload["status"] in {"created", "success"}

    formal_list = api_client.get(
        "/api/v1/publications",
        params={"owner_type": "student", "owner_id": student_id},
    )
    assert formal_list.status_code == 200, formal_list.text
    items = formal_list.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == f"{prefix} Manual Paper"
    assert items[0]["source"] == "manual_upload"

    compat_list = api_client.get(f"/academic-monitor/api/v1/students/{student_id}/papers")
    assert compat_list.status_code == 200, compat_list.text
    compat_items = compat_list.json()["items"]
    assert len(compat_items) == 1
    assert compat_items[0]["title"] == f"{prefix} Manual Paper"


@pytest.mark.asyncio
async def test_candidate_confirm_promotes_into_single_formal_publication(api_client: TestClient):
    prefix = f"test_pub_{uuid4().hex[:10]}"
    await _cleanup_publication_test_rows(prefix)
    _, student_id = await _seed_student(prefix)
    pool = get_pool()

    candidate_id = f"{prefix}_candidate"
    await pool.execute(
        """
        INSERT INTO publication_candidates (
          candidate_id,
          owner_type,
          owner_id,
          target_key,
          canonical_uid,
          title,
          doi,
          abstract,
          publication_date,
          authors,
          affiliations,
          source_type,
          source_details,
          project_group_name,
          compliance_details,
          review_status,
          review_decision,
          first_seen_at,
          last_seen_at,
          affiliation_status,
          compliance_reason,
          matched_tokens,
          checked_affiliations,
          assessed_at
        )
        VALUES (
          $1, 'student', $2, $2, $3, $4, $5, $6, now(),
          $7::jsonb, $8::jsonb, 'monitor_api', $9::jsonb, 'Alpha Group',
          $10::jsonb, 'pending_review', '{}'::jsonb, now(), now(),
          'review_needed', 'needs review', '[]'::jsonb, '[]'::jsonb, now()
        )
        """,
        candidate_id,
        student_id,
        f"doi:{prefix}/confirm",
        f"{prefix} Candidate Paper",
        f"{prefix}/confirm",
        "candidate abstract",
        ["Alice"],
        ["Example University"],
        {"source_providers": ["openalex"], "monitor_id": "monitor_1"},
        {"affiliation_status": "review_needed", "compliance_reason": "needs review"},
    )

    response = api_client.post(
        f"/api/v1/publication-candidates/{candidate_id}/confirm",
        json={"confirmed_by": "tester"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["publication_id"]
    assert body["owner_link_id"]

    compat_list = api_client.get(f"/academic-monitor/api/v1/students/{student_id}/papers")
    assert compat_list.status_code == 200, compat_list.text
    compat_items = compat_list.json()["items"]
    assert len(compat_items) == 1
    assert compat_items[0]["title"] == f"{prefix} Candidate Paper"

    candidate_row = await pool.fetchrow(
        """
        SELECT review_status, promoted_publication_id, promoted_owner_link_id
        FROM publication_candidates
        WHERE candidate_id = $1
        """,
        candidate_id,
    )
    assert candidate_row is not None
    assert candidate_row["review_status"] == "confirmed"
    assert candidate_row["promoted_publication_id"]
    assert candidate_row["promoted_owner_link_id"]


@pytest.mark.asyncio
async def test_student_detail_round_trips_entry_date_and_paper_date_floor(api_client: TestClient):
    prefix = f"test_pub_{uuid4().hex[:10]}"
    await _cleanup_publication_test_rows(prefix)
    _, student_id = await _seed_student(prefix)

    patch_resp = api_client.patch(
        f"/api/v1/students/{student_id}",
        json={
            "entry_date": "2025-03-14",
            "paper_date_floor": "2025-05-14",
            "updated_by": "tester",
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text
    patch_body = patch_resp.json()
    assert patch_body["entry_date"] == "2025-03-14"
    assert patch_body["paper_date_floor"] == "2025-05-14"

    detail_resp = api_client.get(f"/api/v1/students/{student_id}")
    assert detail_resp.status_code == 200, detail_resp.text
    detail_body = detail_resp.json()
    assert detail_body["entry_date"] == "2025-03-14"
    assert detail_body["paper_date_floor"] == "2025-05-14"


@pytest.mark.asyncio
async def test_same_doi_for_student_and_scholar_reuses_single_publication_record(api_client: TestClient):
    prefix = f"test_pub_{uuid4().hex[:10]}"
    await _cleanup_publication_test_rows(prefix)
    scholar_id, student_id = await _seed_student(prefix)

    student_resp = api_client.post(
        "/api/v1/publications/manual",
        json={
            "owner_type": "student",
            "owner_id": student_id,
            "title": f"{prefix} Shared Paper",
            "doi": f"{prefix}/shared",
            "authors": ["Alice"],
            "affiliations": ["Example University"],
        },
    )
    assert student_resp.status_code in {200, 201}, student_resp.text

    scholar_resp = api_client.post(
        "/api/v1/publications/manual",
        json={
            "owner_type": "scholar",
            "owner_id": scholar_id,
            "title": f"{prefix} Shared Paper",
            "doi": f"{prefix}/shared",
            "authors": ["Alice"],
            "affiliations": ["Example University"],
        },
    )
    assert scholar_resp.status_code in {200, 201}, scholar_resp.text

    pool = get_pool()
    publication_count = await pool.fetchval(
        """
        SELECT COUNT(*)::int
        FROM publications
        WHERE canonical_uid = $1
        """,
        f"doi:{prefix}/shared",
    )
    owner_count = await pool.fetchval(
        """
        SELECT COUNT(*)::int
        FROM publication_owners
        WHERE owner_id IN ($1, $2)
        """,
        student_id,
        scholar_id,
    )
    assert publication_count == 1
    assert owner_count == 2
