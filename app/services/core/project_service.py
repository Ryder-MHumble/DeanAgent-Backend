"""Project service — 项目库 CRUD 操作（Supabase SDK，JSON 降级）."""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.project import (
    ProjectDetailResponse,
    ProjectListItem,
    ProjectListResponse,
    ProjectStatsResponse,
)

PROJECTS_FILE = Path("data/scholars/projects.json")

VALID_STATUSES = {"申请中", "在研", "已结题", "暂停", "终止"}
VALID_CATEGORIES = {"国家级", "省部级", "横向课题", "院内课题", "国际合作", "其他"}


class ProjectNotFoundError(ValueError):
    pass


class ProjectAlreadyExistsError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client():
    from app.db.client import get_client  # noqa: PLC0415
    return get_client()


def _load() -> dict[str, Any]:
    if not PROJECTS_FILE.exists():
        return {"last_updated": "", "projects": []}
    with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict[str, Any]) -> None:
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _generate_id() -> str:
    return "proj_" + uuid.uuid4().hex[:8]


def _row_to_dict(row: dict) -> dict:
    """Normalize DB row (JSONB fields may be dicts or strings)."""
    for f in ("related_scholars", "outputs", "cooperation_institutions"):
        v = row.get(f)
        if isinstance(v, str):
            try:
                row[f] = json.loads(v)
            except Exception:
                row[f] = []
        elif v is None:
            row[f] = []
    return row


def _to_list_item(p: dict) -> ProjectListItem:
    return ProjectListItem(
        id=p["id"],
        name=p["name"],
        pi_name=p["pi_name"],
        pi_institution=p.get("pi_institution"),
        funder=p.get("funder"),
        funding_amount=p.get("funding_amount"),
        start_year=p.get("start_year"),
        end_year=p.get("end_year"),
        status=p.get("status", "在研"),
        category=p.get("category"),
        tags=p.get("tags") or [],
    )


def _to_detail(p: dict) -> ProjectDetailResponse:
    from app.schemas.project import ProjectScholar, ProjectOutput  # noqa: PLC0415

    scholars = [
        ProjectScholar(**s) if isinstance(s, dict) else s
        for s in (p.get("related_scholars") or [])
    ]
    outputs = [
        ProjectOutput(**o) if isinstance(o, dict) else o
        for o in (p.get("outputs") or [])
    ]
    return ProjectDetailResponse(
        id=p["id"],
        name=p["name"],
        status=p.get("status", "在研"),
        category=p.get("category"),
        pi_name=p["pi_name"],
        pi_institution=p.get("pi_institution"),
        funder=p.get("funder"),
        funding_amount=p.get("funding_amount"),
        start_year=p.get("start_year"),
        end_year=p.get("end_year"),
        description=p.get("description"),
        keywords=p.get("keywords") or [],
        tags=p.get("tags") or [],
        related_scholars=scholars,
        cooperation_institutions=p.get("cooperation_institutions") or [],
        outputs=outputs,
        created_at=p.get("created_at"),
        updated_at=p.get("updated_at"),
        extra=p.get("extra") or {},
    )


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def list_projects(
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    category: str | None = None,
    funder: str | None = None,
    keyword: str | None = None,
    pi_name: str | None = None,
    tag: str | None = None,
) -> ProjectListResponse:
    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()

        async def _fetch():
            q = client.table("projects").select("*")
            if status:
                q = q.eq("status", status)
            if category:
                q = q.eq("category", category)
            if funder:
                q = q.ilike("funder", f"%{funder}%")
            if pi_name:
                q = q.ilike("pi_name", f"%{pi_name}%")
            if keyword:
                q = q.or_(f"name.ilike.%{keyword}%,description.ilike.%{keyword}%")
            res = await q.execute()
            return res.data or []

        rows = asyncio.get_event_loop().run_until_complete(_fetch())
        rows = [_row_to_dict(r) for r in rows]

        # tag filter (array contains — done in Python for simplicity)
        if tag:
            rows = [r for r in rows if tag in (r.get("tags") or [])]

        total = len(rows)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        items = [_to_list_item(r) for r in rows[start: start + page_size]]
        return ProjectListResponse(total=total, page=page, page_size=page_size,
                                   total_pages=total_pages, items=items)
    except RuntimeError:
        pass
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB list_projects failed: %s", exc)

    # JSON fallback
    data = _load()
    projects = data.get("projects", [])
    if status:
        projects = [p for p in projects if p.get("status") == status]
    if category:
        projects = [p for p in projects if p.get("category") == category]
    if funder:
        funder_lower = funder.lower()
        projects = [p for p in projects if funder_lower in (p.get("funder") or "").lower()]
    if pi_name:
        projects = [p for p in projects if pi_name.lower() in p.get("pi_name", "").lower()]
    if tag:
        projects = [p for p in projects if tag in p.get("tags", [])]
    if keyword:
        kw = keyword.lower()
        projects = [p for p in projects
                    if kw in p.get("name", "").lower()
                    or kw in (p.get("description") or "").lower()]
    total = len(projects)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    items = [_to_list_item(p) for p in projects[start: start + page_size]]
    return ProjectListResponse(total=total, page=page, page_size=page_size,
                               total_pages=total_pages, items=items)


def get_project(project_id: str) -> ProjectDetailResponse | None:
    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()

        async def _fetch():
            res = await client.table("projects").select("*").eq("id", project_id).execute()
            return res.data

        rows = asyncio.get_event_loop().run_until_complete(_fetch())
        if rows:
            return _to_detail(_row_to_dict(rows[0]))
        return None
    except RuntimeError:
        pass
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB get_project failed: %s", exc)

    data = _load()
    for p in data.get("projects", []):
        if p["id"] == project_id:
            return _to_detail(p)
    return None


def get_stats() -> ProjectStatsResponse:
    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()

        async def _fetch():
            res = await client.table("projects").select(
                "status,category,funder,funding_amount"
            ).execute()
            return res.data or []

        rows = asyncio.get_event_loop().run_until_complete(_fetch())
        by_status: dict[str, int] = defaultdict(int)
        by_category: dict[str, int] = defaultdict(int)
        by_funder_count: dict[str, int] = defaultdict(int)
        by_funder_amount: dict[str, float] = defaultdict(float)
        total_funding = 0.0
        active_count = 0
        for r in rows:
            s = r.get("status", "未知")
            by_status[s] += 1
            if s == "在研":
                active_count += 1
            cat = r.get("category") or "未分类"
            by_category[cat] += 1
            funder = r.get("funder") or "未知"
            by_funder_count[funder] += 1
            amount = float(r.get("funding_amount") or 0)
            by_funder_amount[funder] += amount
            total_funding += amount
        return ProjectStatsResponse(
            total=len(rows),
            by_status=[{"status": k, "count": v} for k, v in sorted(by_status.items())],
            by_category=[{"category": k, "count": v} for k, v in sorted(by_category.items())],
            by_funder=[{"funder": k, "count": by_funder_count[k],
                        "total_amount": by_funder_amount[k]} for k in sorted(by_funder_count)],
            total_funding=total_funding,
            active_count=active_count,
        )
    except RuntimeError:
        pass
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB get_stats failed: %s", exc)

    data = _load()
    projects = data.get("projects", [])
    by_status: dict[str, int] = defaultdict(int)
    by_category: dict[str, int] = defaultdict(int)
    by_funder_count: dict[str, int] = defaultdict(int)
    by_funder_amount: dict[str, float] = defaultdict(float)
    total_funding = 0.0
    active_count = 0
    for p in projects:
        s = p.get("status", "未知")
        by_status[s] += 1
        if s == "在研":
            active_count += 1
        cat = p.get("category") or "未分类"
        by_category[cat] += 1
        funder = p.get("funder") or "未知"
        by_funder_count[funder] += 1
        amount = float(p.get("funding_amount") or 0)
        by_funder_amount[funder] += amount
        total_funding += amount
    return ProjectStatsResponse(
        total=len(projects),
        by_status=[{"status": k, "count": v} for k, v in sorted(by_status.items())],
        by_category=[{"category": k, "count": v} for k, v in sorted(by_category.items())],
        by_funder=[{"funder": k, "count": by_funder_count[k],
                    "total_amount": by_funder_amount[k]} for k in sorted(by_funder_count)],
        total_funding=total_funding,
        active_count=active_count,
    )


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def _serialize_for_db(p: dict) -> dict:
    row = {k: v for k, v in p.items()
           if k not in ("keywords", "extra")}  # not in schema
    for f in ("related_scholars", "outputs", "cooperation_institutions"):
        v = row.get(f)
        if isinstance(v, list):
            row[f] = [item.model_dump() if hasattr(item, "model_dump") else item for item in v]
    return row


def create_project(payload: dict[str, Any]) -> ProjectDetailResponse:
    now = datetime.now(timezone.utc).isoformat()
    project_id = _generate_id()
    new_project: dict[str, Any] = {
        "id": project_id,
        "created_at": now,
        "updated_at": now,
        **{k: v for k, v in payload.items() if v is not None},
    }
    for list_field in ("related_scholars", "outputs"):
        if isinstance(new_project.get(list_field), list):
            new_project[list_field] = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in new_project[list_field]
            ]

    # Write to DB
    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()
        asyncio.get_event_loop().run_until_complete(
            client.table("projects").insert(_serialize_for_db(new_project)).execute()
        )
    except RuntimeError:
        pass
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB create_project failed: %s", exc)

    # Always write JSON backup
    data = _load()
    data.setdefault("projects", []).append(new_project)
    _save(data)
    return _to_detail(new_project)


def update_project(project_id: str, updates: dict[str, Any]) -> ProjectDetailResponse | None:
    now = datetime.now(timezone.utc).isoformat()
    clean_updates = {k: v for k, v in updates.items() if v is not None}
    clean_updates["updated_at"] = now
    for list_field in ("related_scholars", "outputs"):
        if isinstance(clean_updates.get(list_field), list):
            clean_updates[list_field] = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in clean_updates[list_field]
            ]

    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()
        db_updates = {k: v for k, v in clean_updates.items() if k not in ("keywords", "extra")}
        res = asyncio.get_event_loop().run_until_complete(
            client.table("projects").update(db_updates).eq("id", project_id).execute()
        )
        if res.data:
            updated = _row_to_dict(res.data[0])
            # Merge back extra fields from JSON for response
            data = _load()
            for p in data.get("projects", []):
                if p["id"] == project_id:
                    p.update(clean_updates)
                    _save(data)
                    updated["keywords"] = p.get("keywords", [])
                    updated["extra"] = p.get("extra", {})
                    break
            return _to_detail(updated)
    except RuntimeError:
        pass
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB update_project failed: %s", exc)

    data = _load()
    for p in data.get("projects", []):
        if p["id"] == project_id:
            p.update(clean_updates)
            _save(data)
            return _to_detail(p)
    return None


def delete_project(project_id: str) -> bool:
    deleted = False
    try:
        import asyncio  # noqa: PLC0415
        client = _get_client()
        res = asyncio.get_event_loop().run_until_complete(
            client.table("projects").delete().eq("id", project_id).execute()
        )
        deleted = bool(res.data)
    except RuntimeError:
        pass
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("DB delete_project failed: %s", exc)

    data = _load()
    original = data.get("projects", [])
    filtered = [p for p in original if p["id"] != project_id]
    if len(filtered) < len(original):
        data["projects"] = filtered
        _save(data)
        return True
    return deleted
