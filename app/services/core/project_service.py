"""Project service — 项目库 CRUD 操作.

数据存储：data/scholars/projects.json
格式：
{
  "last_updated": "ISO8601",
  "projects": [ { ...project fields... } ]
}
"""
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
# Internal I/O helpers
# ---------------------------------------------------------------------------


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
    return uuid.uuid4().hex[:12]


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
        tags=p.get("tags", []),
    )


def _to_detail(p: dict) -> ProjectDetailResponse:
    from app.schemas.project import ProjectScholar, ProjectOutput

    scholars = [
        ProjectScholar(**s) if isinstance(s, dict) else s
        for s in p.get("related_scholars", [])
    ]
    outputs = [
        ProjectOutput(**o) if isinstance(o, dict) else o
        for o in p.get("outputs", [])
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
        keywords=p.get("keywords", []),
        tags=p.get("tags", []),
        related_scholars=scholars,
        cooperation_institutions=p.get("cooperation_institutions", []),
        outputs=outputs,
        created_at=p.get("created_at"),
        updated_at=p.get("updated_at"),
        extra=p.get("extra", {}),
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
    """列出项目（支持过滤和分页）."""
    data = _load()
    projects = data.get("projects", [])

    # 过滤
    if status:
        projects = [p for p in projects if p.get("status") == status]
    if category:
        projects = [p for p in projects if p.get("category") == category]
    if funder:
        funder_lower = funder.lower().replace(" ", "")
        projects = [
            p for p in projects
            if funder_lower in (p.get("funder") or "").lower().replace(" ", "")
        ]
    if pi_name:
        pi_lower = pi_name.lower()
        projects = [
            p for p in projects
            if pi_lower in p.get("pi_name", "").lower()
        ]
    if tag:
        projects = [p for p in projects if tag in p.get("tags", [])]
    if keyword:
        kw = keyword.lower()
        projects = [
            p for p in projects
            if kw in p.get("name", "").lower()
            or kw in (p.get("description") or "").lower()
            or any(kw in k.lower() for k in p.get("keywords", []))
        ]

    total = len(projects)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    items = [_to_list_item(p) for p in projects[start : start + page_size]]

    return ProjectListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )


def get_project(project_id: str) -> ProjectDetailResponse | None:
    """根据 ID 获取项目详情."""
    data = _load()
    for p in data.get("projects", []):
        if p["id"] == project_id:
            return _to_detail(p)
    return None


def get_stats() -> ProjectStatsResponse:
    """项目库统计."""
    data = _load()
    projects = data.get("projects", [])

    by_status: dict[str, int] = defaultdict(int)
    by_category: dict[str, int] = defaultdict(int)
    by_funder_count: dict[str, int] = defaultdict(int)
    by_funder_amount: dict[str, float] = defaultdict(float)
    total_funding = 0.0
    active_count = 0

    for p in projects:
        status = p.get("status", "未知")
        by_status[status] += 1
        if status == "在研":
            active_count += 1

        cat = p.get("category") or "未分类"
        by_category[cat] += 1

        funder = p.get("funder") or "未知"
        by_funder_count[funder] += 1
        amount = p.get("funding_amount") or 0.0
        by_funder_amount[funder] += amount
        total_funding += amount

    return ProjectStatsResponse(
        total=len(projects),
        by_status=[{"status": k, "count": v} for k, v in sorted(by_status.items())],
        by_category=[{"category": k, "count": v} for k, v in sorted(by_category.items())],
        by_funder=[
            {"funder": k, "count": by_funder_count[k], "total_amount": by_funder_amount[k]}
            for k in sorted(by_funder_count.keys())
        ],
        total_funding=total_funding,
        active_count=active_count,
    )


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------


def create_project(payload: dict[str, Any]) -> ProjectDetailResponse:
    """创建项目，自动生成 ID 和时间戳."""
    data = _load()
    now = datetime.now(timezone.utc).isoformat()
    project_id = _generate_id()

    new_project: dict[str, Any] = {
        "id": project_id,
        "created_at": now,
        "updated_at": now,
        **{k: v for k, v in payload.items() if v is not None},
    }

    # 清洗嵌套对象（Pydantic model → dict）
    for list_field in ("related_scholars", "outputs"):
        if isinstance(new_project.get(list_field), list):
            new_project[list_field] = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in new_project[list_field]
            ]

    data.setdefault("projects", []).append(new_project)
    _save(data)
    return _to_detail(new_project)


def update_project(project_id: str, updates: dict[str, Any]) -> ProjectDetailResponse | None:
    """更新项目字段（仅更新传入的字段）."""
    data = _load()
    for p in data.get("projects", []):
        if p["id"] == project_id:
            p.update({k: v for k, v in updates.items() if v is not None})
            p["updated_at"] = datetime.now(timezone.utc).isoformat()

            # 清洗嵌套对象
            for list_field in ("related_scholars", "outputs"):
                if isinstance(p.get(list_field), list):
                    p[list_field] = [
                        item.model_dump() if hasattr(item, "model_dump") else item
                        for item in p[list_field]
                    ]

            _save(data)
            return _to_detail(p)
    return None


def delete_project(project_id: str) -> bool:
    """删除项目，返回 True 表示成功，False 表示未找到."""
    data = _load()
    original = data.get("projects", [])
    filtered = [p for p in original if p["id"] != project_id]
    if len(filtered) == len(original):
        return False
    data["projects"] = filtered
    _save(data)
    return True
