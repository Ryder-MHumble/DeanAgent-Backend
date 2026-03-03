#!/usr/bin/env python3
"""Test script for LLM Faculty Crawler

Usage:
    python scripts/test_llm_faculty.py --source test_tsinghua_air_llm [--dry-run]
"""
import asyncio
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


async def test_llm_crawler(source_id: str, dry_run: bool = False):
    """Test LLM faculty crawler for a specific source"""
    try:
        # Load source config
        source_service = SourceService()
        source_config = source_service.get_source_by_id(source_id)

        if not source_config:
            logger.error("Source %s not found", source_id)
            return False

        logger.info("Testing source: %s (%s)", source_config.get("name"), source_id)
        logger.info("URL: %s", source_config.get("url"))
        logger.info("Crawler class: %s", source_config.get("crawler_class"))

        if dry_run:
            logger.info("[DRY RUN] Would crawl this source")
            return True

        # Create crawler
        crawler = CrawlerRegistry.create_crawler(source_config)
        logger.info("Crawler created: %s", type(crawler).__name__)

        # Run crawler
        logger.info("Starting crawl...")
        items = await crawler.fetch_and_parse()

        logger.info("Crawl completed: %d items extracted", len(items))

        if items:
            logger.info("Sample item:")
            item = items[0]
            logger.info("  Title: %s", item.title)
            logger.info("  URL: %s", item.url)
            logger.info("  Source: %s", item.source_id)
            if item.extra:
                logger.info("  Completeness: %.1f%%", item.extra.get("data_completeness", 0))

        return True

    except Exception as e:
        logger.error("Test failed: %s", e, exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(description="Test LLM Faculty Crawler")
    parser.add_argument("--source", required=True, help="Source ID to test")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")

    args = parser.parse_args()

    success = asyncio.run(test_llm_crawler(args.source, args.dry_run))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
