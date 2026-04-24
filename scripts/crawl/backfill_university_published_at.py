#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="回填高校生态缺失 published_at 的信源，并重建处理产物"
    )
    parser.add_argument(
        "--sources",
        help="逗号分隔的 source_id；默认自动选择所有存在 published_at 缺失的高校信源",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="仅处理缺失量最多的前 N 个信源（与 --sources 二选一时，--sources 优先）",
    )
    parser.add_argument(
        "--skip-rebuild",
        action="store_true",
        help="仅执行重爬回写，不重建 data/processed/university_eco 产物",
    )
    args = parser.parse_args()

    from app.config import settings
    from app.crawlers.utils.playwright_pool import close_browser
    from app.db.client import close_client, init_client
    from app.db.pool import close_pool, init_pool
    from app.services.intel.university.backfill import (
        execute_university_published_at_backfill,
    )

    requested_sources = None
    if args.sources:
        requested_sources = [
            part.strip() for part in args.sources.split(",") if part.strip()
        ]

    await close_client()
    await close_pool()
    await init_pool(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=settings.POSTGRES_DB,
    )
    await init_client(backend="postgres")

    try:
        result = await execute_university_published_at_backfill(
            requested_sources=requested_sources,
            limit=args.limit,
            rebuild_outputs=not args.skip_rebuild,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        await close_browser()
        await close_client()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
