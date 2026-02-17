"""Process raw personnel data through rule-based extraction and optional LLM enrichment.

Tier 1: Rule-based extraction of appointment/dismissal data (always runs).
Tier 2: LLM enrichment with relevance, importance, action suggestions (--enrich flag).

Usage:
    python scripts/process_personnel_intel.py              # Incremental (rules only)
    python scripts/process_personnel_intel.py --force      # Reprocess all
    python scripts/process_personnel_intel.py --dry-run    # Preview extraction
    python scripts/process_personnel_intel.py --enrich     # Add LLM enrichment
    python scripts/process_personnel_intel.py --enrich --force  # Full reprocess + LLM
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BASE_DIR, settings  # noqa: E402
from app.services.intel.personnel.llm import (  # noqa: E402
    default_enrichment,
    enrich_changes_batch,
)
from app.services.intel.personnel.rules import change_id, enrich_by_rules  # noqa: E402
from app.services.json_reader import get_articles  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("process_personnel_intel")

DIMENSION = "personnel"
PROCESSED_DIR = BASE_DIR / "data" / "processed" / "personnel_intel"
ENRICHED_DIR = PROCESSED_DIR / "_enriched"
HASHES_FILE = PROCESSED_DIR / "_processed_hashes.json"
ENRICH_HASHES_FILE = PROCESSED_DIR / "_enriched_hashes.json"


# ---------------------------------------------------------------------------
# Hash tracking
# ---------------------------------------------------------------------------

def load_processed_hashes() -> set[str]:
    if not HASHES_FILE.exists():
        return set()
    try:
        with open(HASHES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("hashes", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_processed_hashes(hashes: set[str]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with open(HASHES_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"hashes": sorted(hashes), "last_run": datetime.now(timezone.utc).isoformat()},
            f, ensure_ascii=False, indent=2,
        )


def load_enriched_hashes() -> set[str]:
    if not ENRICH_HASHES_FILE.exists():
        return set()
    try:
        with open(ENRICH_HASHES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("hashes", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_enriched_hashes(hashes: set[str]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with open(ENRICH_HASHES_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"hashes": sorted(hashes), "last_run": datetime.now(timezone.utc).isoformat()},
            f, ensure_ascii=False, indent=2,
        )


# ---------------------------------------------------------------------------
# Build output records
# ---------------------------------------------------------------------------

def article_date(article: dict) -> str:
    pub = article.get("published_at")
    if pub:
        try:
            return datetime.fromisoformat(pub).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass
    return date.today().isoformat()


def build_feed_item(article: dict, enrichment: dict) -> dict:
    return {
        "id": article.get("url_hash", ""),
        "title": article.get("title", ""),
        "date": article_date(article),
        "source": article.get("source_name", ""),
        "importance": enrichment.get("importance", "一般"),
        "matchScore": enrichment.get("matchScore", 0),
        "changes": enrichment.get("changes", []),
        "sourceUrl": article.get("url", ""),
    }


def build_enriched_change(
    change: dict,
    article: dict,
    llm_enrichment: dict,
) -> dict:
    """Build an enriched change record combining rule extraction + LLM analysis."""
    return {
        "id": change_id(change),
        "name": change.get("name", ""),
        "action": change.get("action", ""),
        "position": change.get("position", ""),
        "department": change.get("department"),
        "date": change.get("date", article_date(article)),
        "source": article.get("source_name", ""),
        "sourceUrl": article.get("url"),
        # LLM enriched fields
        "relevance": llm_enrichment.get("relevance", 10),
        "importance": llm_enrichment.get("importance", "一般"),
        "group": llm_enrichment.get("group", "watch"),
        "note": llm_enrichment.get("note"),
        "actionSuggestion": llm_enrichment.get("actionSuggestion"),
        "background": llm_enrichment.get("background"),
        "signals": llm_enrichment.get("signals", []),
        "aiInsight": llm_enrichment.get("aiInsight"),
    }


# ---------------------------------------------------------------------------
# Enriched data cache I/O
# ---------------------------------------------------------------------------

def save_enriched_article(article: dict, enriched_changes: list[dict]) -> None:
    """Save enriched results for one article to _enriched/ directory."""
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    url_hash = article.get("url_hash", "unknown")
    out = {
        "article": {
            "url_hash": url_hash,
            "title": article.get("title"),
            "url": article.get("url"),
            "published_at": article.get("published_at"),
            "source_id": article.get("source_id"),
            "source_name": article.get("source_name"),
        },
        "enriched_changes": enriched_changes,
    }
    path = ENRICHED_DIR / f"{url_hash}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def load_all_enriched() -> list[dict]:
    """Load all enriched change records from _enriched/ directory."""
    if not ENRICHED_DIR.exists():
        return []
    all_changes: list[dict] = []
    for path in ENRICHED_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            all_changes.extend(data.get("enriched_changes", []))
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning("Skipping invalid enriched file %s: %s", path.name, e)
    return all_changes


# ---------------------------------------------------------------------------
# LLM processing
# ---------------------------------------------------------------------------

async def process_articles_llm(
    articles_with_changes: list[tuple[dict, list[dict]]],
    *,
    concurrency: int = 3,
) -> list[tuple[dict, list[dict]]]:
    """Enrich changes via LLM with concurrency control.

    Input: list of (article, changes) tuples.
    Returns: list of (article, enriched_changes) tuples.
    """
    sem = asyncio.Semaphore(concurrency)
    completed = 0
    start_time = asyncio.get_event_loop().time()
    total = len(articles_with_changes)

    async def _process_one(
        idx: int, article: dict, changes: list[dict],
    ) -> tuple[dict, list[dict]]:
        nonlocal completed
        async with sem:
            title = article.get("title", "?")[:40]
            logger.info(
                "[%d/%d] LLM enriching %d changes: %s",
                idx + 1, total, len(changes), title,
            )

            enrichments = await enrich_changes_batch(changes, article)
            enriched = [
                build_enriched_change(change, article, enrich)
                for change, enrich in zip(changes, enrichments)
            ]

            completed += 1
            elapsed = asyncio.get_event_loop().time() - start_time
            avg = elapsed / completed
            remaining = (total - completed) * avg
            logger.info(
                "  Progress: %d/%d done (%.0fs elapsed, ~%.0fs remaining)",
                completed, total, elapsed, remaining,
            )
            return article, enriched

    tasks = [
        _process_one(i, article, changes)
        for i, (article, changes) in enumerate(articles_with_changes)
    ]
    return list(await asyncio.gather(*tasks))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main_rules_only(args: argparse.Namespace) -> None:
    """Original rule-based processing (no LLM)."""
    articles = get_articles(DIMENSION)
    logger.info("Loaded %d articles from %s", len(articles), DIMENSION)

    # Deduplicate
    seen: set[str] = set()
    unique: list[dict] = []
    for a in articles:
        h = a.get("url_hash", "")
        if h and h not in seen:
            seen.add(h)
            unique.append(a)
    logger.info("Unique articles: %d", len(unique))

    # Filter already processed
    processed_hashes = set() if args.force else load_processed_hashes()
    new_articles = [a for a in unique if a.get("url_hash", "") not in processed_hashes]
    logger.info(
        "New articles: %d (previously processed: %d)",
        len(new_articles), len(processed_hashes),
    )

    if not new_articles and not args.force:
        logger.info("No new articles — rebuilding output from existing data")
        if args.dry_run:
            return
    else:
        for article in (new_articles if not args.force else unique):
            enrichment = enrich_by_rules(article)
            changes = enrichment.get("changes", [])

            if args.dry_run:
                title = article.get("title", "?")[:55]
                logger.info(
                    "  score=%3d imp=%-4s changes=%d  %s",
                    enrichment["matchScore"], enrichment["importance"],
                    len(changes), title,
                )
                for c in changes:
                    logger.info(
                        "    %s %s → %s (%s)",
                        c["action"], c["name"], c["position"],
                        c.get("department") or "?",
                    )
                continue

            h = article.get("url_hash", "")
            if h:
                processed_hashes.add(h)

        if args.dry_run:
            return

        save_processed_hashes(processed_hashes)

    # Rebuild output files
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()

    feed_items: list[dict] = []
    all_changes_final: list[dict] = []

    for article in unique:
        enrichment = enrich_by_rules(article)
        feed_item = build_feed_item(article, enrichment)
        feed_items.append(feed_item)
        all_changes_final.extend(enrichment.get("changes", []))

    feed_items.sort(key=lambda x: x.get("date", ""), reverse=True)
    all_changes_final.sort(key=lambda x: x.get("date", ""), reverse=True)

    feed_path = PROCESSED_DIR / "feed.json"
    with open(feed_path, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": now_iso, "item_count": len(feed_items), "items": feed_items},
            f, ensure_ascii=False, indent=2,
        )
    logger.info("Written %d feed items to %s", len(feed_items), feed_path)

    changes_path = PROCESSED_DIR / "changes.json"
    with open(changes_path, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": now_iso, "item_count": len(all_changes_final),
             "items": all_changes_final},
            f, ensure_ascii=False, indent=2,
        )
    logger.info("Written %d changes to %s", len(all_changes_final), changes_path)
    logger.info("Done (rules only)!")


async def main_with_enrich(args: argparse.Namespace) -> None:
    """Process with LLM enrichment: rules extraction → LLM analysis → enriched_feed.json."""
    articles = get_articles(DIMENSION)
    logger.info("Loaded %d articles from %s", len(articles), DIMENSION)

    # Deduplicate
    seen: set[str] = set()
    unique: list[dict] = []
    for a in articles:
        h = a.get("url_hash", "")
        if h and h not in seen:
            seen.add(h)
            unique.append(a)
    logger.info("Unique articles: %d", len(unique))

    # Run Tier 1 rules on all articles to extract changes
    articles_with_changes: list[tuple[dict, list[dict]]] = []
    total_changes = 0
    for article in unique:
        enrichment = enrich_by_rules(article)
        changes = enrichment.get("changes", [])
        if changes:
            articles_with_changes.append((article, changes))
            total_changes += len(changes)

    logger.info(
        "Tier 1 complete: %d articles with %d total changes (from %d unique articles)",
        len(articles_with_changes), total_changes, len(unique),
    )

    if args.dry_run:
        logger.info("--- DRY RUN: would LLM-enrich %d articles ---", len(articles_with_changes))
        for article, changes in articles_with_changes:
            logger.info(
                "  %d changes: %s",
                len(changes), article.get("title", "?")[:55],
            )
            for c in changes:
                logger.info(
                    "    %s %s → %s (%s)",
                    c["action"], c["name"], c["position"],
                    c.get("department") or "?",
                )
        return

    # Filter already-enriched (incremental)
    enriched_hashes = set() if args.force else load_enriched_hashes()
    new_articles_with_changes = [
        (a, c) for a, c in articles_with_changes
        if a.get("url_hash", "") not in enriched_hashes
    ]

    logger.info(
        "New articles to enrich: %d (previously enriched: %d)",
        len(new_articles_with_changes), len(enriched_hashes),
    )

    # Run LLM enrichment on new articles
    if new_articles_with_changes:
        if not settings.OPENROUTER_API_KEY:
            logger.warning(
                "OPENROUTER_API_KEY not configured — using default enrichment for all"
            )
            for article, changes in new_articles_with_changes:
                enriched = [
                    build_enriched_change(c, article, default_enrichment())
                    for c in changes
                ]
                save_enriched_article(article, enriched)
                h = article.get("url_hash", "")
                if h:
                    enriched_hashes.add(h)
        else:
            logger.info("=" * 60)
            logger.info(
                "LLM enrichment for %d articles (%d changes)",
                len(new_articles_with_changes),
                sum(len(c) for _, c in new_articles_with_changes),
            )
            logger.info("=" * 60)

            results = await process_articles_llm(new_articles_with_changes)
            for article, enriched_changes in results:
                save_enriched_article(article, enriched_changes)
                h = article.get("url_hash", "")
                if h:
                    enriched_hashes.add(h)

        save_enriched_hashes(enriched_hashes)

    # Rebuild enriched_feed.json from all cached enriched data
    all_enriched = load_all_enriched()
    logger.info("Total enriched changes for output: %d", len(all_enriched))

    # Sort: action group first, then by relevance descending
    all_enriched.sort(
        key=lambda x: (
            0 if x.get("group") == "action" else 1,
            -(x.get("relevance") or 0),
            x.get("date", ""),
        ),
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    action_count = sum(1 for x in all_enriched if x.get("group") == "action")

    enriched_path = PROCESSED_DIR / "enriched_feed.json"
    with open(enriched_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": now_iso,
                "total_count": len(all_enriched),
                "action_count": action_count,
                "watch_count": len(all_enriched) - action_count,
                "items": all_enriched,
            },
            f, ensure_ascii=False, indent=2,
        )
    logger.info(
        "Written %d enriched changes to %s (action=%d, watch=%d)",
        len(all_enriched), enriched_path, action_count,
        len(all_enriched) - action_count,
    )

    # Also rebuild rules-only output for backward compat
    main_rules_only(argparse.Namespace(force=True, dry_run=False))
    logger.info("Done (with enrichment)!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Process personnel data")
    parser.add_argument("--force", action="store_true", help="Reprocess all articles")
    parser.add_argument("--dry-run", action="store_true", help="Preview extraction results")
    parser.add_argument("--enrich", action="store_true", help="Enable LLM enrichment (Tier 2)")
    args = parser.parse_args()

    if args.enrich:
        asyncio.run(main_with_enrich(args))
    else:
        main_rules_only(args)


if __name__ == "__main__":
    main()
