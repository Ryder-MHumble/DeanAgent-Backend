"""Institution API — /api/v1/institutions/

统一的机构接口（高校 + 院系）

Endpoints:
  GET    /institutions/{id}       机构详情（高校或院系）
  POST   /institutions/           创建机构（高校或院系）
  PATCH  /institutions/{id}       更新机构
  DELETE /institutions/{id}       删除机构
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
    result = svc.get_institution_detail(institution_id)
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
    summary="创建机构",
    description=(
        "创建新的机构记录（高校或院系），支持三种场景："
        "\n\n**场景 1: 仅创建高校**"
        "\n- 必填：`id`, `name`, `type='university'`"
        "\n- 可选：所有高校字段（category, priority, student_count_24 等）"
        "\n- 不传 `departments` 或传空列表"
        "\n\n**场景 2: 仅创建院系（高校已存在）**"
        "\n- 必填：`id`, `name`, `type='department'`, `parent_id`"
        "\n- `parent_id` 必须是已存在的高校 ID"
        "\n\n**场景 3: 创建高校 + 院系（一次性创建）**"
        "\n- 必填：`id`, `name`, `type='university'`, `departments=[{id, name}, ...]`"
        "\n- 可选：所有高校字段"
        "\n- `departments` 列表中每个院系需提供 `id` 和 `name`"
        "\n\n**重复检测：** 若 `id` 已存在，返回 409 Conflict。院系 ID 必须全局唯一。"
        "\n\n**AMiner org_name 自动填充：** 若未传 `org_name`，"
        "创建完成后会自动调用 AMiner 机构接口查询并写入标准化英文名。"
        "查询失败不影响创建结果，`org_name` 保持为 null。"
    ),
    status_code=201,
)
async def create_institution(body: InstitutionCreate):
    inst_data = body.model_dump()
    try:
        result = svc.create_institution(inst_data)
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
                    updated = svc.update_institution(result.id, {"org_name": fetched_org_name})
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
    result = svc.update_institution(institution_id, updates)
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
    deleted = svc.delete_institution(institution_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Institution '{institution_id}' not found"
        )
