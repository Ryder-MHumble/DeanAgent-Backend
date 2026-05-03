from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill configured paper warehouse sources.")
    parser.add_argument("--source", action="append", help="Specific paper source ID to run")
    parser.add_argument("--dry-run", action="store_true", help="Parse and normalize without writing DB rows")
    args = parser.parse_args()

    from app.config import settings
    from app.crawlers.registry import CrawlerRegistry
    from app.db.pool import close_pool, get_pool, init_pool
    from app.scheduler.manager import load_all_source_configs
    from app.services import paper_service

    await init_pool(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=settings.POSTGRES_DB,
    )
    try:
        configs = [
            cfg
            for cfg in load_all_source_configs()
            if cfg.get("dimension") == "paper" and cfg.get("entity_family") == "paper_record"
        ]
        if args.source:
            source_filter = set(args.source)
            configs = [cfg for cfg in configs if cfg["id"] in source_filter]

        total_inserted = 0
        total_updated = 0
        total_filtered = 0
        for config in configs:
            try:
                crawler = CrawlerRegistry.create_crawler(config)
                result = await crawler.run()
                summary = await paper_service.ingest_crawl_result(
                    get_pool(),
                    result,
                    config,
                    dry_run=args.dry_run,
                )
                total_inserted += summary.inserted_count
                total_updated += summary.updated_count
                total_filtered += summary.filtered_chinese_count
                print(
                    f"{config['id']}: status={summary.status} "
                    f"inserted={summary.inserted_count} updated={summary.updated_count} "
                    f"filtered_chinese={summary.filtered_chinese_count}"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"{config['id']}: status=failed error={exc}")
        print(
            f"total: inserted={total_inserted} updated={total_updated} filtered_chinese={total_filtered}"
        )
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
