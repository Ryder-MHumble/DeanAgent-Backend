"""CLI tool to test a single source crawl."""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def run_crawl(source_id: str, no_db: bool = False):
    from app.crawlers.registry import CrawlerRegistry
    from app.crawlers.utils.json_storage import save_crawl_result_json
    from app.scheduler.manager import load_all_source_configs

    configs = load_all_source_configs()
    config = next((c for c in configs if c["id"] == source_id), None)

    if config is None:
        print(f"Source not found: {source_id}")
        print(f"Available sources: {[c['id'] for c in configs]}")
        return

    print(f"\n=== Crawling: {config.get('name', source_id)} ===")
    print(f"Method: {config.get('crawl_method')}")
    print(f"URL: {config.get('url')}")
    print(f"Mode: {'no-db (JSON only)' if no_db else 'database + JSON'}")
    print()

    crawler = CrawlerRegistry.create_crawler(config)

    if no_db:
        result = await crawler.run(db_session=None)
    else:
        from app.database import async_session_factory

        async with async_session_factory() as session:
            result = await crawler.run(db_session=session)

    print(f"\n=== Results ===")
    print(f"Status: {result.status.value}")
    print(f"Items found: {result.items_total}")
    print(f"Items new: {result.items_new}")
    print(f"Duration: {result.duration_seconds:.1f}s")

    if result.error_message:
        print(f"Error: {result.error_message}")

    # Save to JSON
    json_path = save_crawl_result_json(result, config)
    if json_path:
        print(f"JSON saved to: {json_path}")

    if result.items:
        print(f"\n--- First {min(5, len(result.items))} items ---")
        for item in result.items[:5]:
            print(f"  [{item.published_at or 'no date'}] {item.title}")
            print(f"    URL: {item.url}")
            if item.summary:
                print(f"    Summary: {item.summary[:100]}...")
            print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test crawl a single source")
    parser.add_argument("--source", "-s", required=True, help="Source ID to crawl")
    parser.add_argument(
        "--no-db", action="store_true", help="Skip database, output JSON only"
    )
    args = parser.parse_args()
    asyncio.run(run_crawl(args.source, no_db=args.no_db))
