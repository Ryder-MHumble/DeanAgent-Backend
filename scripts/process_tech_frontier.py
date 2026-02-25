"""Process raw tech data through topic classification and generate frontend-ready JSON.

Tier 1: Rule-based topic classification, heat calculation, signal extraction.
Tier 2: LLM enrichment for topic summaries, insights, and opportunities (optional).

Usage:
    python scripts/process_tech_frontier.py               # Incremental Tier 1
    python scripts/process_tech_frontier.py --force        # Reprocess all
    python scripts/process_tech_frontier.py --dry-run      # Preview classification
    python scripts/process_tech_frontier.py --enrich       # Include LLM enrichment
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BASE_DIR, settings  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("process_tech_frontier")

PROCESSED_DIR = BASE_DIR / "data" / "processed" / "tech_frontier"


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process tech frontier data: topic classification + heat metrics",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocess all articles (ignore hash tracking)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview processing without writing output files",
    )
    parser.add_argument(
        "--enrich", action="store_true",
        help="Run LLM enrichment (Tier 2) after rules processing",
    )
    args = parser.parse_args()

    from app.services.intel.pipeline.tech_frontier_processor import (
        process_tech_frontier_pipeline,
    )

    # ── Tier 1: Rules-based processing ──
    logger.info("=" * 60)
    logger.info("TECH FRONTIER: Tier 1 — Topic classification + heat metrics")
    logger.info("=" * 60)

    if args.dry_run:
        # For dry-run, load data and show classification preview
        from app.services.intel.pipeline.tech_frontier_processor import (
            _deduplicate,
            _load_all_articles,
        )
        from app.services.intel.tech_frontier.rules import (
            TOPICS_CONFIG,
            classify_article,
        )

        articles = _load_all_articles()
        unique = _deduplicate(articles)
        logger.info("Loaded %d articles (%d unique)", len(articles), len(unique))

        # Classification preview
        from collections import Counter
        topic_counts: Counter[str] = Counter()
        unclassified = 0
        for article in unique:
            matches = classify_article(article)
            if matches:
                for m in matches:
                    topic_counts[m["topic_id"]] += 1
            else:
                unclassified += 1

        logger.info("\n--- DRY RUN: Topic Classification Preview ---")
        for config in TOPICS_CONFIG:
            tid = config["id"]
            count = topic_counts.get(tid, 0)
            logger.info(
                "  %-18s (%s): %3d articles",
                config["topic"], tid, count,
            )
        logger.info("  Unclassified: %d", unclassified)
        logger.info("  Total: %d", len(unique))
        return

    result = await process_tech_frontier_pipeline(force=args.force)

    logger.info("\n--- Tier 1 Results ---")
    logger.info("  Total articles loaded: %d", result.get("total_articles", 0))
    logger.info("  Unique articles: %d", result.get("unique", 0))
    logger.info("  New processed: %d", result.get("new_processed", 0))
    logger.info("  Topics: %d", result.get("topics", 0))
    logger.info("  Opportunities: %d", result.get("opportunities", 0))
    logger.info("  Weekly signals: %d", result.get("weekly_signals", 0))

    breakdown = result.get("topic_breakdown", {})
    if breakdown:
        logger.info("\n  Topic breakdown:")
        for tid, count in sorted(breakdown.items(), key=lambda x: -x[1]):
            logger.info("    %-18s: %d", tid, count)

    # Show output file paths
    logger.info("\nOutput files:")
    for fname in ["topics.json", "opportunities.json", "stats.json"]:
        path = PROCESSED_DIR / fname
        if path.exists():
            size = path.stat().st_size
            logger.info("  %s (%d bytes)", path, size)

    # ── Tier 2: LLM enrichment (optional) ──
    if args.enrich:
        if not settings.OPENROUTER_API_KEY:
            logger.warning(
                "OPENROUTER_API_KEY not configured — skipping LLM enrichment"
            )
            return

        logger.info("\n" + "=" * 60)
        logger.info("TECH FRONTIER: Tier 2 — LLM enrichment")
        logger.info("=" * 60)

        from app.services.intel.pipeline.tech_frontier_processor import (
            process_tech_frontier_llm_enrichment,
        )

        llm_result = await process_tech_frontier_llm_enrichment()
        logger.info("LLM enrichment result: %s", llm_result)

    logger.info("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
