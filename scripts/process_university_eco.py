#!/usr/bin/env python3
"""Process university ecosystem data — generate overview, feed, and research outputs.

Usage:
    python scripts/process_university_eco.py             # incremental
    python scripts/process_university_eco.py --force     # reprocess all
    python scripts/process_university_eco.py --dry-run   # preview only
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Process university ecosystem data")
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocess all articles (ignore processed hashes)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview processing without writing output files",
    )
    args = parser.parse_args()

    if args.dry_run:
        # Dry-run: just show stats
        from app.services.intel.university.rules import classify_article
        from app.services.json_reader import get_articles

        articles = get_articles("universities")
        seen: set[str] = set()
        unique = []
        for a in articles:
            h = a.get("url_hash", "")
            if h and h not in seen:
                seen.add(h)
                unique.append(a)

        classified = 0
        type_counts: dict[str, int] = {"论文": 0, "专利": 0, "获奖": 0}
        for article in unique:
            result = classify_article(article)
            if result:
                classified += 1
                type_counts[result["type"]] += 1
                if classified <= 5:
                    print(
                        f"  [{result['type']}] [{result['influence']}] "
                        f"{result['institution']} — {article['title'][:60]}"
                    )

        print("\n--- DRY RUN ---")
        print(f"Total articles: {len(articles)}")
        print(f"Unique articles: {len(unique)}")
        print(f"Research classified: {classified}")
        print(f"  论文: {type_counts['论文']}")
        print(f"  专利: {type_counts['专利']}")
        print(f"  获奖: {type_counts['获奖']}")
        print(f"Unclassified: {len(unique) - classified}")
        return

    from app.services.intel.pipeline.university_eco_processor import (
        process_university_eco_pipeline,
    )

    result = await process_university_eco_pipeline(force=args.force)
    print("\n--- RESULT ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
