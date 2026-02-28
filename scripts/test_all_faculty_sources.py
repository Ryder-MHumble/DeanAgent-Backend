#!/usr/bin/env python3
"""Test all enabled faculty sources and generate a report.

Usage:
    python scripts/test_all_faculty_sources.py
    python scripts/test_all_faculty_sources.py --verbose
"""
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.crawlers.registry import CrawlerRegistry
from app.scheduler.manager import load_all_source_configs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def test_source(source_config: dict) -> dict:
    """Test a single faculty source and return results."""
    source_id = source_config["id"]
    source_name = source_config["name"]

    result = {
        "source_id": source_id,
        "source_name": source_name,
        "university": source_config.get("university", ""),
        "department": source_config.get("department", ""),
        "status": "unknown",
        "items_count": 0,
        "duration": 0.0,
        "error": None,
        "data_completeness_avg": 0,
    }

    start_time = time.time()

    try:
        crawler = CrawlerRegistry.create_crawler(source_config)
        items = await crawler.fetch_and_parse()

        result["status"] = "success"
        result["items_count"] = len(items)
        result["duration"] = time.time() - start_time

        # Calculate average data completeness
        if items:
            completeness_scores = [
                item.extra.get("data_completeness", 0)
                for item in items
                if item.extra
            ]
            if completeness_scores:
                result["data_completeness_avg"] = sum(completeness_scores) / len(completeness_scores)

        logger.info(
            "✓ %s: %d items, %.1fs, completeness=%.1f%%",
            source_id, len(items), result["duration"], result["data_completeness_avg"]
        )

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        result["duration"] = time.time() - start_time
        logger.error("✗ %s: %s", source_id, e)

    return result


async def main():
    """Test all enabled faculty sources."""
    verbose = "--verbose" in sys.argv

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load all source configs
    all_sources = load_all_source_configs()

    # Filter for enabled faculty sources
    faculty_sources = [
        src for src in all_sources
        if src.get("dimension") == "university_faculty"
        and src.get("is_enabled", False)
    ]

    print(f"\n{'='*80}")
    print(f"Testing {len(faculty_sources)} enabled faculty sources")
    print(f"{'='*80}\n")

    results = []

    for i, source in enumerate(faculty_sources, 1):
        print(f"[{i}/{len(faculty_sources)}] Testing {source['id']}...")
        result = await test_source(source)
        results.append(result)

        # Small delay between sources to avoid rate limiting
        await asyncio.sleep(2)

    # Generate summary report
    print(f"\n{'='*80}")
    print("SUMMARY REPORT")
    print(f"{'='*80}\n")

    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    total_items = sum(r["items_count"] for r in results)
    avg_completeness = sum(r["data_completeness_avg"] for r in results) / len(results) if results else 0

    print(f"Total sources tested: {len(results)}")
    print(f"Successful: {success_count} ({success_count/len(results)*100:.1f}%)")
    print(f"Failed: {failed_count} ({failed_count/len(results)*100:.1f}%)")
    print(f"Total faculty records: {total_items}")
    print(f"Average data completeness: {avg_completeness:.1f}%")
    print()

    # Group by university
    by_university = {}
    for r in results:
        univ = r["university"]
        if univ not in by_university:
            by_university[univ] = []
        by_university[univ].append(r)

    print("By University:")
    for univ, sources in sorted(by_university.items()):
        success = sum(1 for s in sources if s["status"] == "success")
        items = sum(s["items_count"] for s in sources)
        print(f"  {univ}: {success}/{len(sources)} sources, {items} faculty")
    print()

    # Show failed sources
    if failed_count > 0:
        print("Failed Sources:")
        for r in results:
            if r["status"] == "failed":
                print(f"  ✗ {r['source_id']}: {r['error']}")
        print()

    # Show low completeness sources (< 50%)
    low_completeness = [r for r in results if r["status"] == "success" and r["data_completeness_avg"] < 50]
    if low_completeness:
        print(f"Low Completeness Sources (< 50%):")
        for r in sorted(low_completeness, key=lambda x: x["data_completeness_avg"]):
            print(f"  {r['source_id']}: {r['data_completeness_avg']:.1f}% ({r['items_count']} items)")
        print()

    # Save detailed report to JSON
    report_path = Path("data/reports/faculty_test_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total": len(results),
                "success": success_count,
                "failed": failed_count,
                "total_items": total_items,
                "avg_completeness": avg_completeness,
            },
            "results": results,
        }, f, indent=2, ensure_ascii=False)

    print(f"Detailed report saved to: {report_path}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
