"""Scholar API — /api/v1/scholars/

Endpoints:
  GET  /scholars/                                       学者列表（分页 + 多维度筛选）
  GET  /scholars/stats                                  统计数据
  GET  /scholars/sources                                信源列表
  POST /scholars/                                       手动创建学者
  GET  /scholars/{url_hash}                             单条学者详情
  DELETE /scholars/{url_hash}                           删除学者记录
  PATCH /scholars/{url_hash}/basic                      更新基础信息（直接修改原始 JSON）
  PATCH /scholars/{url_hash}/relation                   更新「与两院关系」字段（用户管理）
  POST  /faculty/{url_hash}/updates                    新增用户备注动态
  DELETE /scholars/{url_hash}/updates/{update_idx}      删除用户备注动态
  PATCH /scholars/{url_hash}/achievements               更新学术成就（论文、专利、奖项）
  GET  /scholars/{url_hash}/students                    查询指导学生列表
  POST /scholars/{url_hash}/students                    新增指导学生
  GET  /scholars/{url_hash}/students/{student_id}       查询单名学生详情
  PATCH /scholars/{url_hash}/students/{student_id}      更新学生信息
  DELETE /scholars/{url_hash}/students/{student_id}     删除学生记录
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.scholar import (
    AchievementUpdate,
    ScholarBasicUpdate,
    ScholarCreateRequest,
    ScholarDetailResponse,
    ScholarListResponse,
    ScholarStatsResponse,
    InstituteRelationUpdate,
    UserUpdateCreate,
)
from app.schemas.supervised_student import (
    SupervisedStudentCreate,
    SupervisedStudentListResponse,
    SupervisedStudentResponse,
    SupervisedStudentUpdate,
)
from app.services import scholar_service as svc
from app.services.stores import supervised_student_store as student_store

router = APIRouter()


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=ScholarListResponse,
    summary="学者列表",
    description=(
        "获取 scholars 维度下的学者列表，支持按高校、院系、职称、"
        "学术称号、关键词、数据完整度及信源过滤，按姓名升序排列。"
    ),
)
async def list_scholars(
    university: str | None = Query(None, description="高校名称（模糊匹配）"),
    department: str | None = Query(None, description="院系名称（模糊匹配）"),
    position: str | None = Query(
        None, description="职称（精确匹配，如 教授/副教授/研究员/助理教授）"
    ),
    is_academician: bool | None = Query(None, description="仅显示院士"),
    is_potential_recruit: bool | None = Query(None, description="仅显示潜在招募对象"),
    is_advisor_committee: bool | None = Query(None, description="仅显示顾问委员会成员"),
    has_email: bool | None = Query(None, description="仅显示有邮箱联系方式的学者"),
    keyword: str | None = Query(
        None, description="关键词搜索（姓名/英文名/bio/研究方向/关键词）"
    ),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
):
    return svc.get_scholar_list(
        university=university,
        department=department,
        position=position,
        is_academician=is_academician,
        is_potential_recruit=is_potential_recruit,
        is_advisor_committee=is_advisor_committee,
        has_email=has_email,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/stats",
    response_model=ScholarStatsResponse,
    summary="学者统计",
    description="返回学者库总览统计：总数、院士数、潜在招募数、按高校/职称分布、完整度分布。",
)
async def get_stats():
    return svc.get_scholar_stats()


@router.post(
    "/",
    response_model=ScholarDetailResponse,
    summary="手动创建学者",
    description=(
        "手动创建一条新的学者记录。只有 name 是必填字段，其他字段均可选。"
        "自动检测重复（同名 + 同机构 + 同联系方式），重复时返回 409 Conflict。"
        "成功创建后返回完整的学者详情（包含自动生成的 url_hash）。"
    ),
    status_code=201,
)
async def create_scholar(body: ScholarCreateRequest):
    from app.services.scholar._create import create_scholar as create_scholar_svc

    detail, error = create_scholar_svc(body.model_dump())

    if error.startswith("duplicate:"):
        existing_hash = error.split(":", 1)[1]
        raise HTTPException(
            status_code=409,
            detail=f"Scholar already exists with url_hash: {existing_hash}",
        )
    if error:
        raise HTTPException(status_code=400, detail=error)

    return detail


@router.get(
    "/{url_hash}",
    response_model=ScholarDetailResponse,
    summary="学者详情",
    description="根据 url_hash 获取单条学者完整数据（爬虫字段 + 用户标注合并）。",
)
async def get_faculty(url_hash: str):
    result = svc.get_scholar_detail(url_hash)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Faculty '{url_hash}' not found")
    return result


# ---------------------------------------------------------------------------
# Write endpoints (user-managed fields only)
# ---------------------------------------------------------------------------


@router.patch(
    "/{url_hash}/basic",
    response_model=ScholarDetailResponse,
    summary="更新基础信息",
    description=(
        "更新指定学者的基础信息字段（名称、职称、简介、联系方式、学术链接、教育经历等）。"
        "直接修改原始 JSON 文件（data/raw/scholars/.../latest.json）。"
        "所有字段均可选，仅传入需要修改的字段；传 null 或不传则保持不变。"
        "列表字段（research_areas/keywords/academic_titles/education 等）"
        "传入 [] 表示清空，传入非空列表则完全替换。"
        "返回更新后的完整 faculty detail（包含 annotations 合并结果）。"
    ),
)
async def update_basic(url_hash: str, body: ScholarBasicUpdate):
    updates = body.model_dump(exclude_none=True)
    result = svc.update_scholar_basic(url_hash, updates)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Faculty '{url_hash}' not found")
    return result


@router.patch(
    "/{url_hash}/relation",
    response_model=ScholarDetailResponse,
    summary="更新与两院关系",
    description=(
        "更新指定学者的「与两院关系」字段（顾问委员会、兼职导师、潜在招募等）。"
        "所有字段均可选，仅传入需要修改的字段。relation_updated_at 由服务端自动填写。"
        "这些字段永不被爬虫覆盖。"
    ),
)
async def update_relation(url_hash: str, body: InstituteRelationUpdate):
    updates = body.model_dump(exclude_none=True)
    result = svc.update_scholar_relation(url_hash, updates)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Faculty '{url_hash}' not found")
    return result


@router.post(
    "/{url_hash}/updates",
    response_model=ScholarDetailResponse,
    summary="新增用户备注动态",
    description=(
        "为指定学者新增一条用户录入的动态备注（获奖/项目立项/任职履新等）。"
        "added_by 自动转换为 'user:{added_by}'，created_at 由服务端自动填写。"
    ),
    status_code=201,
)
async def add_update(url_hash: str, body: UserUpdateCreate):
    result = svc.add_scholar_update(url_hash, body.model_dump())
    if result is None:
        raise HTTPException(status_code=404, detail=f"Faculty '{url_hash}' not found")
    return result


@router.delete(
    "/{url_hash}",
    summary="删除学者记录",
    description="删除指定的学者记录及其所有关联数据。",
    status_code=204,
)
async def delete_scholar(url_hash: str):
    deleted = svc.delete_scholar(url_hash)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Faculty '{url_hash}' not found")


@router.delete(
    "/{url_hash}/updates/{update_idx}",
    response_model=ScholarDetailResponse,
    summary="删除用户备注动态",
    description=(
        "删除指定学者的用户备注动态（按 user_updates 列表中的索引）。"
        "只能删除 added_by 以 'user:' 开头的条目；尝试删除爬虫动态将返回 403。"
    ),
)
async def delete_update(url_hash: str, update_idx: int):
    try:
        result = svc.delete_scholar_update(url_hash, update_idx)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail=f"Faculty '{url_hash}' not found")
    return result


@router.patch(
    "/{url_hash}/achievements",
    response_model=ScholarDetailResponse,
    summary="更新学术成就",
    description=(
        "更新指定学者的学术成就字段（代表性论文、专利、获奖）。"
        "每个字段传入后会完全替换（而非追加），传 null 或不传则保持不变。"
        "这些字段由用户维护，但爬虫也可自动填充初始值。"
        "achievements_updated_at 由服务端自动填写。"
    ),
)
async def update_achievements(url_hash: str, body: AchievementUpdate):
    updates = body.model_dump(exclude_none=True)
    result = svc.update_scholar_achievements(url_hash, updates)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Faculty '{url_hash}' not found")
    return result


# ---------------------------------------------------------------------------
# Supervised students CRUD
# ---------------------------------------------------------------------------


def _assert_faculty_exists(url_hash: str) -> None:
    """Raise 404 if the faculty member does not exist."""
    if svc.get_scholar_detail(url_hash) is None:
        raise HTTPException(status_code=404, detail=f"Faculty '{url_hash}' not found")


@router.get(
    "/{url_hash}/students",
    response_model=SupervisedStudentListResponse,
    summary="查询指导学生列表",
    description="返回指定导师下的所有指导学生记录（联合培养学生）。",
)
async def list_students(url_hash: str):
    _assert_faculty_exists(url_hash)
    students = student_store.list_students(url_hash)
    return SupervisedStudentListResponse(
        total=len(students),
        faculty_url_hash=url_hash,
        items=students,
    )


@router.post(
    "/{url_hash}/students",
    response_model=SupervisedStudentResponse,
    summary="新增指导学生",
    description=(
        "为指定导师新增一名指导学生记录。"
        "id / created_at / updated_at 由服务端自动生成，added_by 自动补充为 'user:{added_by}'。"
    ),
    status_code=201,
)
async def add_student(url_hash: str, body: SupervisedStudentCreate):
    _assert_faculty_exists(url_hash)
    record = student_store.add_student(url_hash, body.model_dump())
    return record


@router.get(
    "/{url_hash}/students/{student_id}",
    response_model=SupervisedStudentResponse,
    summary="查询单名学生详情",
    description="根据学生记录 ID 获取单名指导学生的完整信息。",
)
async def get_student(url_hash: str, student_id: str):
    _assert_faculty_exists(url_hash)
    record = student_store.get_student(url_hash, student_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found")
    return record


@router.patch(
    "/{url_hash}/students/{student_id}",
    response_model=SupervisedStudentResponse,
    summary="更新学生信息",
    description=(
        "部分更新指定学生记录。所有字段均可选，传 null 或不传则保持不变。"
        "updated_at 由服务端自动更新。"
    ),
)
async def update_student(url_hash: str, student_id: str, body: SupervisedStudentUpdate):
    _assert_faculty_exists(url_hash)
    updates = body.model_dump(exclude_none=True)
    record = student_store.update_student(url_hash, student_id, updates)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found")
    return record


@router.delete(
    "/{url_hash}/students/{student_id}",
    summary="删除学生记录",
    description="删除指定导师下的一条学生记录。",
    status_code=204,
)
async def delete_student(url_hash: str, student_id: str):
    _assert_faculty_exists(url_hash)
    deleted = student_store.delete_student(url_hash, student_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found")
