"""Batch crawl all enabled sources, optionally filtered by dimension. Outputs JSON only (no DB)."""
import argparse
import asyncio
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_batch(dimension: str | None = None, concurrency: int = 3):
    from app.crawlers.registry import CrawlerRegistry
    from app.crawlers.utils.json_storage import save_crawl_result_json
    from app.scheduler.manager import load_all_source_configs

    configs = load_all_source_configs()

    # Filter by dimension if specified
    if dimension:
        configs = [c for c in configs if c.get("dimension") == dimension]

    # Only enabled sources
    configs = [c for c in configs if c.get("is_enabled", True)]

    if not configs:
        print(f"No enabled sources found" + (f" for dimension '{dimension}'" if dimension else ""))
        return

    # Group by dimension for reporting
    by_dimension: dict[str, list[dict]] = defaultdict(list)
    for c in configs:
        by_dimension[c.get("dimension", "unknown")].append(c)

    print(f"\n{'=' * 60}")
    print(f"Batch Crawl — {len(configs)} sources across {len(by_dimension)} dimensions")
    for dim, sources in sorted(by_dimension.items()):
        print(f"  {dim}: {len(sources)} sources")
    print(f"{'=' * 60}\n")

    # Track results
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "failed": 0, "items": 0})
    semaphore = asyncio.Semaphore(concurrency)

    async def crawl_one(config: dict):
        source_id = config["id"]
        dim = config.get("dimension", "unknown")

        async with semaphore:
            try:
                crawler = CrawlerRegistry.create_crawler(config)
                result = await crawler.run(db_session=None)

                # Save JSON
                json_path = save_crawl_result_json(result, config)

                status_str = result.status.value
                items_count = result.items_total

                if result.error_message:
                    stats[dim]["failed"] += 1
                    print(f"  FAIL  {source_id}: {result.error_message[:80]}")
                else:
                    stats[dim]["success"] += 1
                    stats[dim]["items"] += items_count
                    print(
                        f"  OK    {source_id}: {items_count} items "
                        f"({result.duration_seconds:.1f}s)"
                        + (f" -> {json_path}" if json_path else "")
                    )

            except Exception as e:
                stats[dim]["failed"] += 1
                print(f"  ERROR {source_id}: {e}")

    # Run all crawls with concurrency limit
    start_time = time.monotonic()

    for dim in sorted(by_dimension.keys()):
        print(f"\n--- {dim} ({len(by_dimension[dim])} sources) ---")
        tasks = [crawl_one(config) for config in by_dimension[dim]]
        await asyncio.gather(*tasks)

    elapsed = time.monotonic() - start_time

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"SUMMARY (total time: {elapsed:.1f}s)")
    print(f"{'=' * 60}")

    total_success = 0
    total_failed = 0
    total_items = 0

    for dim in sorted(stats.keys()):
        s = stats[dim]
        total_success += s["success"]
        total_failed += s["failed"]
        total_items += s["items"]
        print(
            f"  {dim:25s}: {s['success']:3d} ok, {s['failed']:3d} failed, "
            f"{s['items']:5d} items"
        )

    print(f"  {'TOTAL':25s}: {total_success:3d} ok, {total_failed:3d} failed, "
          f"{total_items:5d} items")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch crawl sources to JSON")
    parser.add_argument(
        "--dimension", "-d",
        help="Filter by dimension (e.g., technology, national_policy)",
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int, default=3,
        help="Max concurrent crawls (default: 3)",
    )
    args = parser.parse_args()
    asyncio.run(run_batch(dimension=args.dimension, concurrency=args.concurrency))
