"""Unified social_posts table APIs."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from app.schemas.common import PaginatedResponse
from app.schemas.social_post import SocialPostBrief, SocialPostDetail, SocialPostStats
from app.services import social_post_service
from app.services.intel.source_filter import parse_source_filter

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[SocialPostBrief],
    summary="社媒帖子列表",
    description="查询统一社媒帖子库，支持平台/信源/作者/关键词过滤与分页排序。",
)
async def list_social_posts(
    source_id: str | None = Query(None, description="按单个信源 ID 筛选（精确匹配）"),
    source_ids: str | None = Query(None, description="按多个信源 ID 筛选（逗号分隔，精确匹配）"),
    source_name: str | None = Query(None, description="按单个信源名称筛选（模糊匹配）"),
    source_names: str | None = Query(None, description="按多个信源名称筛选（逗号分隔，模糊匹配）"),
    platform: str | None = Query(None, description="平台过滤，如 x/youtube/linkedin"),
    username: str | None = Query(None, description="作者用户名（去掉 @）"),
    post_type: Literal["post", "reply", "repost", "quote", "comment"] | None = Query(
        None,
        description="帖子类型过滤",
    ),
    is_kol_author: bool | None = Query(None, description="是否仅返回 KOL 作者内容"),
    keyword: str | None = Query(None, description="正文/作者关键词搜索"),
    sort_by: Literal[
        "published_at",
        "crawled_at",
        "like_count",
        "reply_count",
        "repost_count",
        "quote_count",
        "view_count",
        "bookmark_count",
        "created_at",
    ] = Query("published_at", description="排序字段"),
    order: Literal["asc", "desc"] = Query("desc", description="排序方向"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
):
    source_filter = parse_source_filter(source_id, source_ids, source_name, source_names)
    return await social_post_service.list_social_posts(
        source_filter=source_filter,
        platform=platform,
        username=username,
        post_type=post_type,
        is_kol_author=is_kol_author,
        keyword=keyword,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/stats",
    response_model=list[SocialPostStats],
    summary="社媒帖子统计",
    description="按平台/信源/作者/帖子类型/日期聚合统计。",
)
async def get_social_post_stats(
    group_by: Literal["platform", "source", "author", "post_type", "day"] = Query(
        "platform",
        description="聚合维度",
    ),
):
    return await social_post_service.get_social_post_stats(group_by=group_by)


@router.get(
    "/{post_id}",
    response_model=SocialPostDetail,
    summary="社媒帖子详情",
    description="根据帖子 ID 获取详情，返回帖子和内嵌热门回复。",
)
async def get_social_post_detail(
    post_id: str,
    top_replies_limit: int = Query(5, ge=0, le=20, description="返回热门回复条数"),
):
    post = await social_post_service.get_social_post(
        post_id,
        top_replies_limit=top_replies_limit,
    )
    if post is None:
        raise HTTPException(status_code=404, detail="Social post not found")
    return post
