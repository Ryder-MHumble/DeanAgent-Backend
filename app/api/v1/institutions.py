"""Institution API — /api/v1/institutions/

统一的机构接口（高校 + 院系），支持自动 ID 生成和 AMiner 标准化名自动填充

Endpoints:
  GET    /institutions/aminer/search-org    搜索 AMiner 机构名（辅助创建）
  GET    /institutions/{id}                 机构详情（高校或院系）
  POST   /institutions/                     创建机构（ID 自动生成）
  PATCH  /institutions/{id}                 更新机构
  DELETE /institutions/{id}                 删除机构
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.schemas.institution import (
    InstitutionCreate,
    InstitutionDetailResponse,
    InstitutionUpdate,
)
from app.services import institution_service as svc
from app.services.core.institution_service import InstitutionAlreadyExistsError

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper endpoints (must come before /{institution_id} to avoid catch-all)
# ---------------------------------------------------------------------------


@router.get(
    "/aminer/search-org",
    summary="搜索 AMiner 机构名",
    description=(
        "搜索 AMiner 数据库中的机构信息，获取标准化的英文机构名（org_name）。"
        "\n\n此端点用于辅助机构创建：用户在创建高校或院系时，可先调用此接口查询"
        "对应的 AMiner 标准化名称，然后在创建请求中传入 `org_name` 字段。"
        "\n\n**Query Parameters:**"
        "\n- `q` (required): 机构名称（中文或英文均可），如 '清华大学' 或 'Tsinghua'"
        "\n- `size` (optional, default=5): 返回的结果数量，最多 10 个"
        "\n\n**返回示例：**"
        "\n```json"
        "\n{"
        "\n  \"query\": \"清华大学\","
        "\n  \"total\": 3,"
        "\n  \"items\": ["
        "\n    {\"id\": \"...\", \"name\": \"清华大学\", \"name_en\": \"Tsinghua University\", \"country\": \"China\"},"
        "\n    {\"id\": \"...\", \"name\": \"清华大学\", \"name_en\": \"Tsinghua Univ.\", \"country\": \"China\"}"
        "\n  ]"
        "\n}"
        "\n```"
    ),
)
async def search_aminer_organizations(q: str, size: int = 5):
    """搜索 AMiner 机构名."""
    if not q or not q.strip():
        raise HTTPException(
            status_code=400, detail="Query parameter 'q' is required and cannot be empty"
        )

    if size < 1 or size > 10:
        size = min(max(size, 1), 10)

    try:
        from app.services.external.aminer_client import get_aminer_client

        client = get_aminer_client()
        resp = await client.search_organizations(q, size=size)

        # Normalize response
        items = resp.get("data", [])
        return {
            "query": q,
            "total": len(items),
            "items": items,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"AMiner API configuration error: {exc}",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("AMiner search failed for '%s': %s", q, exc)
        raise HTTPException(
            status_code=502,
            detail=f"AMiner search failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{institution_id}",
    response_model=InstitutionDetailResponse,
    summary="机构详情",
    description=(
        "根据机构 ID 获取完整机构信息。"
        "\n\n**高校详情包含：**"
        "\n- 基本信息（分类、优先级、学生数、导师数）"
        "\n- 人员信息（驻院领导、委员会、校领导、重要学者）"
        "\n- 合作信息（联合实验室、培养合作、学术合作、人才双聘）"
        "\n- 院系列表"
        "\n\n**院系详情包含：**"
        "\n- 基本信息（名称、学者数）"
        "\n- 信源列表（source_id, source_name, scholar_count, is_enabled）"
    ),
)
async def get_institution(institution_id: str):
    result = await svc.get_institution_detail(institution_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Institution '{institution_id}' not found"
        )
    return result


# ---------------------------------------------------------------------------
# Write endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=InstitutionDetailResponse,
    summary="创建机构（支持简化模式）",
    description=(
        "创建新的机构记录（高校或院系）。**ID 不提供会自动生成**，让你专注于填写关键信息。"
        "\n\n## 三种使用场景"
        "\n\n### 场景 1: 新增高校（最简单）"
        "\n```json"
        "\n{\"name\": \"清华大学\", \"type\": \"university\"}"
        "\n```"
        "\nBody 最少字段：`name`, `type='university'`"
        "\n- `id` 不提供会自动生成（如 'qinghua'）"
        "\n- 可选：category, priority, student_count_24/25, 人员和合作信息等"
        "\n\n### 场景 2: 新增院系（需选择高校）"
        "\n```json"
        "\n{\"name\": \"计算机科学与技术系\", \"type\": \"department\", \"parent_id\": \"qinghua\"}"
        "\n```"
        "\nBody 必填字段：`name`, `type='department'`, `parent_id`"
        "\n- `id` 不提供会自动生成"
        "\n- `parent_id` 必须是已存在的高校 ID（可先用 GET /institutions/ 查询）"
        "\n\n### 场景 3: 一次性创建高校+多个院系"
        "\n```json"
        "\n{"
        "\n  \"name\": \"北京大学\","
        "\n  \"type\": \"university\","
        "\n  \"departments\": ["
        "\n    {\"name\": \"计算机学院\"},"
        "\n    {\"name\": \"信息科学技术学院\"}"
        "\n  ]"
        "\n}"
        "\n```"
        "\n- 高校和所有院系的 ID 都会自动生成"
        "\n\n## 功能特性"
        "\n\n**自动生成 ID** — 从机构名称自动生成简洁易记的 ID（如 '清华' → 'qinghua'）"
        "\n\n**AMiner 标准化名** — 创建后自动调用 AMiner 机构搜索接口填充 `org_name`，"
        "获取标准化的英文机构名。查询失败不影响创建。"
        "\n\n**冲突检测** — 若 ID 已存在，返回 409 Conflict。院系 ID 必须全局唯一。"
    ),
    status_code=201,
)
async def create_institution(body: InstitutionCreate):
    inst_data = body.model_dump()
    try:
        result = await svc.create_institution(inst_data)
    except InstitutionAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 若 org_name 未传入，自动从 AMiner 查询并写回
    if not inst_data.get("org_name"):
        try:
            from app.services.external.aminer_client import get_aminer_client

            client = get_aminer_client()
            aminer_resp = await client.search_organizations(body.name)
            orgs = aminer_resp.get("data", [])
            if orgs:
                fetched_org_name = orgs[0].get("name_en") or orgs[0].get("name")
                if fetched_org_name:
                    updated = await svc.update_institution(result.id, {"org_name": fetched_org_name})
                    if updated:
                        result = updated
                        logger.info(
                            "AMiner org_name auto-filled for '%s': %s",
                            result.id,
                            fetched_org_name,
                        )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "AMiner org_name lookup failed for '%s' (%s): %s",
                body.name,
                body.id,
                exc,
            )

    return result


@router.patch(
    "/{institution_id}",
    response_model=InstitutionDetailResponse,
    summary="更新机构",
    description=(
        "更新指定机构的信息。所有字段均可选，仅传入需要修改的字段。"
        "\n\n**高校可更新字段：**"
        "\n- 基本信息：name, category, priority"
        "\n- 学生导师：student_count_24, student_count_25, mentor_count"
        "\n- 人员信息：resident_leaders, degree_committee, teaching_committee, "
        "university_leaders, notable_scholars"
        "\n- 合作信息：key_departments, joint_labs, training_cooperation, "
        "academic_cooperation, talent_dual_appointment, recruitment_events, "
        "visit_exchanges, cooperation_focus"
        "\n\n**院系可更新字段：**"
        "\n- name"
    ),
)
async def update_institution(institution_id: str, body: InstitutionUpdate):
    updates = body.model_dump(exclude_none=True)
    result = await svc.update_institution(institution_id, updates)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Institution '{institution_id}' not found"
        )
    return result


@router.delete(
    "/{institution_id}",
    summary="删除机构",
    description=(
        "删除指定的机构记录。"
        "\n\n**注意：**"
        "\n- 删除高校会同时删除其下所有院系"
        "\n- 删除院系不影响父高校"
    ),
    status_code=204,
)
async def delete_institution(institution_id: str):
    deleted = await svc.delete_institution(institution_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Institution '{institution_id}' not found"
        )
