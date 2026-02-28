#!/usr/bin/env python3
"""Enrich faculty data using LLM to extract and refine fields.

This script reads raw faculty data from data/raw/university_faculty/,
uses LLM to intelligently extract and map fields, and saves enriched
data to data/processed/university_faculty/.

Usage:
    python scripts/enrich_faculty_data.py                    # Process all sources
    python scripts/enrich_faculty_data.py --source <id>      # Process single source
    python scripts/enrich_faculty_data.py --dry-run          # Preview without saving
    python scripts/enrich_faculty_data.py --force            # Re-process all items
"""
import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.crawlers.utils.faculty_llm_extractor import extract_faculty_fields_with_llm
from app.schemas.scholar import ScholarRecord, compute_scholar_completeness

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def enrich_faculty_item(item: dict, force: bool = False) -> dict:
    """Enrich a single faculty item using LLM.

    Args:
        item: Raw CrawledItem dict with 'extra' containing ScholarRecord
        force: If True, re-process even if already enriched

    Returns:
        Enriched item dict
    """
    extra = item.get("extra", {})

    # Skip if already enriched (unless force=True)
    if not force and extra.get("_llm_enriched"):
        logger.debug("Skipping already enriched item: %s", extra.get("name"))
        return item

    # Extract raw fields
    raw_name = item.get("title", "")
    raw_bio = item.get("content", "")
    raw_position = extra.get("position", "")

    # Use LLM to extract and refine fields
    try:
        llm_fields = await extract_faculty_fields_with_llm(
            raw_name=raw_name,
            raw_bio=raw_bio,
            raw_position=raw_position,
            detail_html_text="",  # Could fetch detail page if needed
        )

        # Merge LLM-extracted fields into extra
        extra.update({
            "name": llm_fields.get("name", raw_name),
            "name_en": llm_fields.get("name_en", ""),
            "position": llm_fields.get("position", raw_position),
            "research_areas": llm_fields.get("research_areas", extra.get("research_areas", [])),
            "academic_titles": llm_fields.get("academic_titles", []),
            "is_academician": llm_fields.get("is_academician", False),
            "bio": llm_fields.get("bio", raw_bio),
            "email": llm_fields.get("email") or extra.get("email", ""),
            "phone": llm_fields.get("phone") or extra.get("phone", ""),
            "office": llm_fields.get("office") or extra.get("office", ""),
            "phd_institution": llm_fields.get("phd_institution", ""),
            "phd_year": llm_fields.get("phd_year", ""),
            "_llm_enriched": True,
        })

        # Recalculate data completeness
        record = ScholarRecord(**extra)
        extra["data_completeness"] = compute_scholar_completeness(record)

        # Update item
        item["extra"] = extra
        item["title"] = extra["name"]  # Update title with cleaned name

        logger.info(
            "Enriched %s: position=%s, research_areas=%d, completeness=%d%%",
            extra["name"], extra["position"],
            len(extra["research_areas"]), extra["data_completeness"]
        )

    except Exception as e:
        logger.error("Failed to enrich %s: %s", raw_name, e)

    return item


async def enrich_source(source_id: str, dry_run: bool = False, force: bool = False) -> dict:
    """Enrich all faculty items from a single source.

    Args:
        source_id: Source ID (e.g., 'tsinghua_cs_faculty')
        dry_run: If True, don't save results
        force: If True, re-process all items

    Returns:
        Dict with processing stats
    """
    # Find raw data file
    raw_dir = Path("data/raw/university_faculty")
    raw_files = list(raw_dir.rglob(f"{source_id}/latest.json"))

    if not raw_files:
        logger.warning("No raw data found for source: %s", source_id)
        return {"status": "not_found", "items_processed": 0}

    raw_file = raw_files[0]
    logger.info("Processing %s from %s", source_id, raw_file)

    # Load raw data
    with open(raw_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    if not items:
        logger.warning("No items found in %s", raw_file)
        return {"status": "empty", "items_processed": 0}

    # Enrich each item
    enriched_items = []
    for i, item in enumerate(items, 1):
        logger.info("[%d/%d] Processing %s...", i, len(items), item.get("title", ""))
        enriched_item = await enrich_faculty_item(item, force=force)
        enriched_items.append(enriched_item)

        # Rate limiting: small delay between LLM calls
        await asyncio.sleep(0.5)

    # Save enriched data
    if not dry_run:
        output_dir = Path("data/processed/university_faculty") / source_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "enriched.json"

        enriched_data = {
            "source_id": source_id,
            "total_items": len(enriched_items),
            "items": enriched_items,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(enriched_data, f, indent=2, ensure_ascii=False)

        logger.info("Saved enriched data to %s", output_file)

    # Calculate stats
    avg_completeness = sum(
        item["extra"].get("data_completeness", 0)
        for item in enriched_items
    ) / len(enriched_items) if enriched_items else 0

    return {
        "status": "success",
        "items_processed": len(enriched_items),
        "avg_completeness": avg_completeness,
    }


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Enrich faculty data with LLM")
    parser.add_argument("--source", help="Process single source ID")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--force", action="store_true", help="Re-process all items")
    args = parser.parse_args()

    if args.source:
        # Process single source
        result = await enrich_source(args.source, dry_run=args.dry_run, force=args.force)
        print(f"\nResult: {result}")
    else:
        # Process all sources
        raw_dir = Path("data/raw/university_faculty")
        source_dirs = [d for d in raw_dir.rglob("*/latest.json")]

        print(f"\nFound {len(source_dirs)} faculty sources to process\n")

        results = []
        for i, raw_file in enumerate(source_dirs, 1):
            source_id = raw_file.parent.name
            print(f"[{i}/{len(source_dirs)}] Processing {source_id}...")

            result = await enrich_source(source_id, dry_run=args.dry_run, force=args.force)
            results.append({"source_id": source_id, **result})

        # Summary
        print(f"\n{'='*80}")
        print("ENRICHMENT SUMMARY")
        print(f"{'='*80}\n")

        success_count = sum(1 for r in results if r["status"] == "success")
        total_items = sum(r.get("items_processed", 0) for r in results)
        avg_completeness = sum(r.get("avg_completeness", 0) for r in results) / len(results) if results else 0

        print(f"Sources processed: {len(results)}")
        print(f"Successful: {success_count}")
        print(f"Total items enriched: {total_items}")
        print(f"Average completeness: {avg_completeness:.1f}%")
        print()


if __name__ == "__main__":
    asyncio.run(main())
