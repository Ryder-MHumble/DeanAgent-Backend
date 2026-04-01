"""Unified social KOL APIs."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.schemas.social_kol import (
    SocialAccountListResponse,
    SocialIngestResponse,
    SocialPostDetailResponse,
    SocialPostListResponse,
    SocialTwitterIngestRequest,
)
from app.services.external import social_kol_service

router = APIRouter()


@router.post(
    "/ingest/twitter",
    response_model=SocialIngestResponse,
    summary="导入 Twitter/KOL 聚合数据",
    description=(
        "将 twitterapi.io 聚合结果（最新帖子 + 每帖热门回复）导入统一社媒表。\n\n"
        "输入推荐直接复用我们当前的本地 JSON 结构。"
    ),
)
async def ingest_twitter_bundle(body: SocialTwitterIngestRequest):
    return await social_kol_service.ingest_twitter_bundle(body)


@router.get(
    "/accounts",
    response_model=SocialAccountListResponse,
    summary="账号列表",
    description="查询统一社媒账号库，支持平台/关键词/KOL 标记过滤。",
)
async def list_accounts(
    platform: str | None = Query(None, description="平台过滤，如 x/linkedin/youtube"),
    keyword: str | None = Query(None, description="用户名/显示名/Bio 关键词"),
    is_kol: bool | None = Query(None, description="是否只看 KOL 账号"),
    sort_by: Literal[
        "last_seen_at",
        "follower_count",
        "created_at",
        "username",
    ] = Query("last_seen_at", description="排序字段"),
    sort_order: Literal["asc", "desc"] = Query("desc", description="排序方向"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    return await social_kol_service.list_accounts(
        platform=platform,
        keyword=keyword,
        is_kol=is_kol,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/posts",
    response_model=SocialPostListResponse,
    summary="帖子列表",
    description=(
        "查询统一社媒帖子表。默认返回 KOL 主帖（post_type=post, is_kol_author=true）。\n"
        "可按账号、关键词等过滤。"
    ),
)
async def list_posts(
    platform: str | None = Query(None, description="平台过滤，如 x/linkedin/youtube"),
    username: str | None = Query(None, description="作者用户名"),
    post_type: Literal["post", "reply", "repost", "quote", "comment"] | None = Query(
        "post",
        description="帖子类型过滤",
    ),
    is_kol_author: bool | None = Query(True, description="是否仅返回 KOL 作者内容"),
    keyword: str | None = Query(None, description="正文/作者关键词搜索"),
    sort_by: Literal[
        "published_at",
        "like_count",
        "reply_count",
        "repost_count",
        "view_count",
        "created_at",
    ] = Query("published_at", description="排序字段"),
    sort_order: Literal["asc", "desc"] = Query("desc", description="排序方向"),
    include_top_replies: bool = Query(
        False,
        description="是否附带每条主帖的热门回复（写入 post.top_replies）",
    ),
    top_replies_limit: int = Query(5, ge=1, le=20, description="每条主帖附带回复条数"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    return await social_kol_service.list_posts(
        platform=platform,
        username=username,
        post_type=post_type,
        is_kol_author=is_kol_author,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        include_top_replies=include_top_replies,
        top_replies_limit=top_replies_limit,
    )


@router.get(
    "/posts/{platform}/{external_post_id}",
    response_model=SocialPostDetailResponse,
    summary="帖子详情（含热门回复）",
    description="按平台 + 帖子外部 ID 获取帖子详情，并返回热门回复。",
    responses={404: {"description": "Post not found"}},
)
async def get_post_detail(
    platform: str,
    external_post_id: str,
    top_replies_limit: int = Query(5, ge=1, le=20, description="返回热门回复条数"),
):
    result = await social_kol_service.get_post_detail(
        platform=platform,
        external_post_id=external_post_id,
        top_replies_limit=top_replies_limit,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return result
