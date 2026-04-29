#!/usr/bin/env python3
"""Crawl X(Twitter) accounts via twitterapi.io and ingest into social tables.

Defaults come from source YAML so operation can be tuned without code changes.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

from app.config import BASE_DIR, settings
from app.db.client import close_client, init_client
from app.db.pool import close_pool, init_pool
from app.schemas.social_kol import SocialTwitterIngestRequest
from app.services.external.social_kol_service import ingest_twitter_bundle

BASE_URL = "https://api.twitterapi.io/twitter"


def _load_source_config(source_id: str) -> dict[str, Any]:
    sources_dir = settings.SOURCES_DIR if settings.SOURCES_DIR else (BASE_DIR / "sources")
    for yaml_file in sorted(Path(sources_dir).rglob("*.yaml")):
        if not yaml_file.is_file():
            continue
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        for source in data.get("sources", []) or []:
            if str(source.get("id") or "").strip() == source_id:
                row = dict(source)
                row.setdefault("source_file", yaml_file.name)
                row.setdefault(
                    "source_file_path",
                    yaml_file.relative_to(Path(sources_dir)).as_posix(),
                )
                return row
    raise ValueError(f"Source not found in YAML: {source_id}")


def _load_accounts(accounts_file: Path, cohort: str) -> list[dict[str, Any]]:
    raw = yaml.safe_load(accounts_file.read_text(encoding="utf-8")) or {}
    accounts = raw.get("accounts", []) if isinstance(raw, dict) else []

    parsed: list[dict[str, Any]] = []
    for item in accounts:
        if not isinstance(item, dict):
            continue
        username = str(item.get("username") or "").strip().lstrip("@")
        if not username:
            continue
        item_cohort = str(item.get("cohort") or "").strip().lower() or "core"
        if cohort != "all" and item_cohort != cohort:
            continue
        parsed.append(
            {
                "username": username,
                "name": str(item.get("name") or username).strip(),
                "category": str(item.get("category") or "").strip() or None,
                "cohort": item_cohort,
            }
        )

    dedup: dict[str, dict[str, Any]] = {}
    for item in parsed:
        key = item["username"].lower()
        dedup.setdefault(key, item)
    return list(dedup.values())


async def _fetch_user_posts(
    client: httpx.AsyncClient,
    username: str,
    max_posts: int,
    include_replies: bool,
) -> dict[str, Any] | None:
    resp = await client.get(
        f"{BASE_URL}/user/last_tweets",
        params={
            "userName": username,
            "includeReplies": "true" if include_replies else "false",
        },
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "success":
        return None

    data_block = data.get("data")
    tweets: list[dict[str, Any]] = []
    if isinstance(data_block, dict):
        raw_tweets = data_block.get("tweets", [])
        if isinstance(raw_tweets, list):
            tweets = [t for t in raw_tweets if isinstance(t, dict)]

    tweets = tweets[:max_posts]

    author = (tweets[0].get("author") or {}) if tweets else {}
    matched_username = str(author.get("userName") or username).strip().lstrip("@")
    display_name = str(author.get("name") or "").strip() or None

    return {
        "query_username": username,
        "matched_username": matched_username,
        "display_name": display_name,
        "latest_5_posts": tweets,
    }


async def _run(args: argparse.Namespace) -> None:
    source_cfg = _load_source_config(args.source_id)

    accounts_file_str = args.accounts_file or source_cfg.get("twitter_accounts_file")
    if not accounts_file_str:
        raise ValueError("twitter_accounts_file is not configured in source YAML")

    accounts_file = Path(str(accounts_file_str))
    if not accounts_file.is_absolute():
        candidate = settings.SOURCES_DIR / accounts_file
        accounts_file = candidate if candidate.exists() else (BASE_DIR / accounts_file)

    cohort = args.cohort or str(source_cfg.get("crawl_accounts_cohort") or "all").strip().lower()
    max_posts = (
        args.max_posts
        if args.max_posts is not None
        else int(source_cfg.get("max_tweets_per_account", 3) or 3)
    )
    include_replies = (
        args.include_replies
        if args.include_replies is not None
        else bool(source_cfg.get("include_replies", True))
    )
    top_replies_per_post = (
        args.reply_limit
        if args.reply_limit is not None
        else int(source_cfg.get("max_replies_per_post", 5) or 5)
    )

    accounts = _load_accounts(accounts_file, cohort)
    if args.limit > 0:
        accounts = accounts[: args.limit]

    if not accounts:
        print("No accounts selected; nothing to crawl.")
        return

    if not settings.TWITTER_API_KEY:
        raise RuntimeError("TWITTER_API_KEY is not configured")

    headers = {"x-api-key": settings.TWITTER_API_KEY, "Accept": "application/json"}
    proxy = None if args.ignore_proxy else (settings.TWITTER_API_PROXY or None)

    users: list[dict[str, Any]] = []
    failed: list[str] = []

    async with httpx.AsyncClient(timeout=45.0, headers=headers, proxy=proxy) as client:
        for account in accounts:
            username = account["username"]
            try:
                user_block = await _fetch_user_posts(
                    client,
                    username,
                    max_posts,
                    include_replies,
                )
                if not user_block:
                    failed.append(username)
                    continue
                user_block["category"] = account.get("category")
                user_block["cohort"] = account.get("cohort")
                users.append(user_block)
            except Exception:
                failed.append(username)

    fetched_at_utc = datetime.now(timezone.utc).isoformat()
    payload_dict = {
        "platform": "x",
        "fetched_at_utc": fetched_at_utc,
        "max_posts_per_user": max_posts,
        "top_replies_per_post": top_replies_per_post,
        "include_replies": include_replies,
        "users": users,
    }

    out_dir = BASE_DIR / "data" / "raw" / "social_kol"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_file = out_dir / f"twitter_bundle_{cohort}_{ts}.json"
    out_file.write_text(json.dumps(payload_dict, ensure_ascii=False, indent=2), encoding="utf-8")

    if settings.POSTGRES_DSN:
        await init_pool(dsn=settings.POSTGRES_DSN)
    else:
        await init_pool(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
        )
    await init_client(backend="postgres")

    try:
        ingest_req = SocialTwitterIngestRequest.model_validate(payload_dict)
        result = await ingest_twitter_bundle(ingest_req)
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        print(f"effective_source={args.source_id}")
        print(
            "effective_config="
            f"cohort={cohort},max_posts={max_posts},include_replies={include_replies},"
            f"reply_limit={top_replies_per_post}"
        )
        print(f"raw_saved={out_file}")
        print(f"users_fetched={len(users)} failed={len(failed)}")
        if failed:
            print("failed_accounts=" + ",".join(failed))
    finally:
        await close_client()
        await close_pool()


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl and ingest X KOL accounts")
    parser.add_argument(
        "--source-id",
        default="twitter_ai_kol_international",
        help="Source ID in sources/**/*.yaml",
    )
    parser.add_argument(
        "--accounts-file",
        default=None,
        help="Path to account yaml (default: read twitter_accounts_file from source yaml)",
    )
    parser.add_argument(
        "--cohort",
        default=None,
        choices=["core", "expansion", "all"],
        help="Which cohort to crawl (default: read crawl_accounts_cohort from source yaml)",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=None,
        help="Max posts/account (default: read max_tweets_per_account from source yaml)",
    )
    parser.add_argument(
        "--reply-limit",
        type=int,
        default=None,
        help="Max embedded replies/post (default: read max_replies_per_post from source yaml)",
    )
    parser.add_argument(
        "--include-replies",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Whether to include replies (default: read include_replies from source yaml)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max accounts to crawl (0=all)")
    parser.add_argument(
        "--ignore-proxy",
        action="store_true",
        help="Ignore TWITTER_API_PROXY and connect directly",
    )

    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
