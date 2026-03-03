#!/usr/bin/env python3
"""Integration test for YMSC and LLM Faculty Crawlers

Usage:
    python scripts/test_faculty_crawlers.py [--crawler ymsc|llm] [--dry-run]
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import argparse
from app.crawlers.registry import CrawlerRegistry
from app.services.source_service import SourceService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def test_crawler(source_id: str, dry_run: bool = False):
    """Test a faculty crawler"""
    try:
        # Load source config
        source_service = SourceService()
        source_config = source_service.get_source_by_id(source_id)

        if not source_config:
            logger.error("Source %s not found", source_id)
            return False

        logger.info("=" * 80)
        logger.info("Testing source: %s", source_config.get("name"))
        logger.info("Source ID: %s", source_id)
        logger.info("URL: %s", source_config.get("url"))
        logger.info("Crawler class: %s", source_config.get("crawler_class"))
        logger.info("=" * 80)

        if dry_run:
            logger.info("[DRY RUN] Would crawl this source")
            return True

        # Create crawler
        try:
            crawler = CrawlerRegistry.create_crawler(source_config)
            logger.info("✓ Crawler created: %s", type(crawler).__name__)
        except Exception as e:
            logger.error("✗ Failed to create crawler: %s", e)
            return False

        # Run crawler
        logger.info("Starting crawl...")
        try:
            items = await asyncio.wait_for(crawler.fetch_and_parse(), timeout=300.0)
        except asyncio.TimeoutError:
            logger.error("✗ Crawl timed out after 300 seconds")
            return False
        except Exception as e:
            logger.error("✗ Crawl failed: %s", e, exc_info=True)
            return False

        logger.info("✓ Crawl completed: %d items extracted", len(items))

        if items:
            logger.info("\nSample items:")
            for i, item in enumerate(items[:3]):
                logger.info(f"\n  [{i+1}] {item.title}")
                logger.info(f"      URL: {item.url}")
                logger.info(f"      Source: {item.source_id}")
                if item.extra:
                    completeness = item.extra.get("data_completeness", 0)
                    logger.info(f"      Completeness: {completeness:.1f}%")
                    if item.extra.get("email"):
                        logger.info(f"      Email: {item.extra.get('email')}")
                    if item.extra.get("position"):
                        logger.info(f"      Position: {item.extra.get('position')}")

            # Save sample output
            output_file = Path(f"test_output_{source_id}.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump([item.model_dump() for item in items[:3]], f, indent=2, ensure_ascii=False)
            logger.info(f"\n✓ Sample output saved to {output_file}")

        logger.info("\n" + "=" * 80)
        logger.info("✓ Test passed!")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error("✗ Test failed: %s", e, exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Faculty Crawlers")
    parser.add_argument(
        "--crawler",
        choices=["ymsc", "llm"],
        default="ymsc",
        help="Crawler to test (default: ymsc)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")

    args = parser.parse_args()

    # Map crawler type to source ID
    source_map = {
        "ymsc": "tsinghua_ymsc_faculty",
        "llm": "test_tsinghua_air_llm",
    }

    source_id = source_map[args.crawler]
    success = asyncio.run(test_crawler(source_id, args.dry_run))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
