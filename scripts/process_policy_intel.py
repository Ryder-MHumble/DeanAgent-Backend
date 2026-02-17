"""Process raw policy data through two-tier enrichment and generate frontend-ready JSON.

Tier 1: Rule-based scoring for ALL articles (fast, no API calls).
Tier 2: LLM enrichment only for articles with matchScore >= threshold.

Usage:
    python scripts/process_policy_intel.py                   # Incremental (two-tier)
    python scripts/process_policy_intel.py --force           # Reprocess all
    python scripts/process_policy_intel.py --dry-run         # Preview Tier 1 scoring
    python scripts/process_policy_intel.py --limit 3         # Process N articles
    python scripts/process_policy_intel.py --threshold 50    # Custom LLM threshold
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BASE_DIR, settings  # noqa: E402
from app.services.intel.policy.llm import (  # noqa: E402
    default_enrichment,
    enrich_article_lite,
)
from app.services.intel.policy.rules import enrich_by_rules  # noqa: E402
from app.services.json_reader import get_articles  # noqa: E402
from app.services.llm_service import LLMError  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("process_policy_intel")

DIMENSIONS = ["national_policy", "beijing_policy", "personnel"]
PROCESSED_DIR = BASE_DIR / "data" / "processed" / "policy_intel"
ENRICHED_DIR = PROCESSED_DIR / "_enriched"
HASHES_FILE = PROCESSED_DIR / "_processed_hashes.json"


# ---------------------------------------------------------------------------
# Category / status helpers
# ---------------------------------------------------------------------------

def determine_category(
    article: dict, llm_result: dict,
) -> str:
    """Assign frontend category based on dimension + LLM analysis."""
    if llm_result.get("isOpportunity"):
        return "政策机会"
    dim = article.get("dimension", "")
    group = article.get("group", "")
    if dim == "personnel":
        return "领导讲话"
    if dim == "beijing_policy" and group == "news_personnel":
        return "领导讲话"
    if dim == "beijing_policy":
        return "北京政策"
    if dim == "national_policy":
        return "国家政策"
    return "一般"


def determine_agency_type(article: dict) -> str:
    """Map dimension to agencyType for PolicyItem."""
    dim = article.get("dimension", "")
    if dim == "national_policy":
        return "national"
    if dim == "beijing_policy":
        return "beijing"
    return "ministry"


def compute_status(days_left: int | None) -> str:
    """Derive status from daysLeft for PolicyItem."""
    if days_left is None:
        return "tracking"
    if days_left <= 7:
        return "urgent"
    if days_left <= 30:
        return "active"
    return "tracking"


def article_date(article: dict) -> str:
    """Extract YYYY-MM-DD date from article.

    Priority: published_at → URL-embedded date → today (last resort).
    """
    pub = article.get("published_at")
    if pub:
        try:
            return datetime.fromisoformat(pub).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass
    # Fallback: extract date from URL (common in gov websites)
    url = article.get("url", "")
    m = re.search(r'/t(\d{4})(\d{2})(\d{2})_', url)
    if m:
        return f"{m[1]}-{m[2]}-{m[3]}"
    m = re.search(r'/(\d{4})(\d{2})/t\d+', url)
    if m:
        return f"{m[1]}-{m[2]}-01"
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Build output records
# ---------------------------------------------------------------------------

def build_feed_item(article: dict, llm: dict) -> dict:
    """Build a PolicyFeedItem dict from article + LLM enrichment."""
    category = determine_category(article, llm)
    original_tags = article.get("tags", [])
    llm_tags = llm.get("tags", [])
    merged_tags = list(dict.fromkeys(original_tags + llm_tags))

    return {
        "id": article.get("url_hash", ""),
        "title": article.get("title", ""),
        "summary": llm.get("summary", ""),
        "category": category,
        "importance": llm.get("importance", "一般"),
        "date": article_date(article),
        "source": article.get("source_name", ""),
        "tags": merged_tags,
        "matchScore": llm.get("matchScore"),
        "funding": llm.get("funding"),
        "daysLeft": llm.get("daysLeft"),
        "leader": llm.get("leader"),
        "relevance": llm.get("relevance"),
        "signals": llm.get("signals") or None,
        "sourceUrl": article.get("url", ""),
        "aiInsight": llm.get("aiInsight") or None,
        "detail": llm.get("detail") or None,
        "content": article.get("content") or None,
    }


def build_opportunity_item(article: dict, llm: dict) -> dict | None:
    """Build a PolicyItem dict if the article is an opportunity."""
    if not llm.get("isOpportunity"):
        return None
    days_left = llm.get("daysLeft")
    return {
        "id": article.get("url_hash", ""),
        "name": article.get("title", ""),
        "agency": llm.get("agency", article.get("source_name", "")),
        "agencyType": determine_agency_type(article),
        "matchScore": llm.get("matchScore", 0),
        "funding": llm.get("funding") or "待确认",
        "deadline": llm.get("deadline") or "待确认",
        "daysLeft": days_left if days_left is not None else 999,
        "status": compute_status(days_left),
        "aiInsight": llm.get("aiInsight", ""),
        "detail": llm.get("detail", ""),
        "sourceUrl": article.get("url", ""),
    }


# ---------------------------------------------------------------------------
# Hash tracking
# ---------------------------------------------------------------------------

def load_processed_hashes() -> set[str]:
    """Load set of already-processed url_hashes."""
    if not HASHES_FILE.exists():
        return set()
    try:
        with open(HASHES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("hashes", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_processed_hashes(hashes: set[str]) -> None:
    """Persist processed url_hashes."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with open(HASHES_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"hashes": sorted(hashes), "last_run": datetime.now(timezone.utc).isoformat()},
            f,
            ensure_ascii=False,
            indent=2,
        )


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

async def process_articles_llm(
    articles: list[dict],
    tier1_map: dict[str, dict],
    *,
    concurrency: int = 3,
) -> list[tuple[dict, dict]]:
    """Enrich articles via LLM (Tier 2) with concurrency control and ETA.

    ``tier1_map`` maps url_hash → Tier 1 rule-based result so the LLM
    can refine it.

    Returns list of (article, llm_result) tuples.
    """
    sem = asyncio.Semaphore(concurrency)
    completed = 0
    start_time = asyncio.get_event_loop().time()

    async def _process_one(idx: int, article: dict) -> tuple[dict, dict]:
        nonlocal completed
        async with sem:
            title = article.get("title", "?")[:40]
            url_hash = article.get("url_hash", "")
            tier1 = tier1_map.get(url_hash, default_enrichment(article))
            logger.info("[%d/%d] LLM processing: %s", idx + 1, len(articles), title)
            try:
                llm_result = await enrich_article_lite(article, tier1)
            except LLMError as e:
                logger.warning("  LLM failed for %s: %s — using Tier 1 result", title, e)
                llm_result = tier1

            completed += 1
            elapsed = asyncio.get_event_loop().time() - start_time
            avg = elapsed / completed
            remaining = (len(articles) - completed) * avg
            logger.info(
                "  LLM progress: %d/%d done (%.0fs elapsed, ~%.0fs remaining)",
                completed, len(articles), elapsed, remaining,
            )
            return article, llm_result

    tasks = [_process_one(i, a) for i, a in enumerate(articles)]
    results = await asyncio.gather(*tasks)
    return list(results)


def save_enriched(article: dict, llm_result: dict) -> None:
    """Save individual enriched result for debugging/incremental rebuild."""
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
            "dimension": article.get("dimension"),
            "group": article.get("group"),
            "tags": article.get("tags", []),
            "content": article.get("content"),
        },
        "llm": llm_result,
    }
    path = ENRICHED_DIR / f"{url_hash}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def load_all_enriched() -> list[tuple[dict, dict]]:
    """Load all enriched article files from _enriched/ directory."""
    if not ENRICHED_DIR.exists():
        return []
    results = []
    for path in ENRICHED_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            results.append((data["article"], data["llm"]))
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning("Skipping invalid enriched file %s: %s", path.name, e)
    return results


def rebuild_output_files(all_enriched: list[tuple[dict, dict]]) -> None:
    """Regenerate feed.json and opportunities.json from all enriched data."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Build feed items
    feed_items = []
    opportunity_items = []
    for article, llm in all_enriched:
        feed_item = build_feed_item(article, llm)
        feed_items.append(feed_item)

        opp = build_opportunity_item(article, llm)
        if opp:
            opportunity_items.append(opp)

    # Sort feed by date descending
    feed_items.sort(key=lambda x: x.get("date", ""), reverse=True)
    # Sort opportunities by daysLeft ascending
    opportunity_items.sort(key=lambda x: x.get("daysLeft", 999))

    # Write feed.json
    feed_path = PROCESSED_DIR / "feed.json"
    with open(feed_path, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": now_iso, "item_count": len(feed_items), "items": feed_items},
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info("Written %d items to %s", len(feed_items), feed_path)

    # Write opportunities.json
    opp_path = PROCESSED_DIR / "opportunities.json"
    with open(opp_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": now_iso,
                "item_count": len(opportunity_items),
                "items": opportunity_items,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info("Written %d items to %s", len(opportunity_items), opp_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(description="Process policy data through LLM enrichment")
    parser.add_argument("--force", action="store_true", help="Reprocess all articles")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    parser.add_argument("--limit", type=int, default=0, help="Max articles to process (0=all)")
    parser.add_argument(
        "--dimension",
        choices=DIMENSIONS,
        help="Process only one dimension",
    )
    parser.add_argument(
        "--threshold", type=int, default=40,
        help="Min rule-based matchScore for LLM enrichment (default: 40)",
    )
    args = parser.parse_args()

    # Load raw articles
    dims = [args.dimension] if args.dimension else DIMENSIONS
    all_articles: list[dict] = []
    for dim in dims:
        articles = get_articles(dim)
        logger.info("Loaded %d articles from %s", len(articles), dim)
        all_articles.extend(articles)

    logger.info("Total raw articles: %d", len(all_articles))

    # Deduplicate by url_hash (in case of overlap)
    seen: set[str] = set()
    unique_articles: list[dict] = []
    for a in all_articles:
        h = a.get("url_hash", "")
        if h and h not in seen:
            seen.add(h)
            unique_articles.append(a)
    logger.info("Unique articles: %d", len(unique_articles))

    # Filter out already-processed
    processed_hashes = set() if args.force else load_processed_hashes()
    new_articles = [
        a for a in unique_articles if a.get("url_hash", "") not in processed_hashes
    ]
    logger.info(
        "New articles to process: %d (previously processed: %d)",
        len(new_articles),
        len(processed_hashes),
    )

    if args.limit > 0:
        new_articles = new_articles[:args.limit]
        logger.info("Limited to %d articles", len(new_articles))

    # ── Tier 1: Rule-based scoring for ALL articles ──
    if new_articles:
        logger.info("=" * 60)
        logger.info("TIER 1: Rule-based scoring for %d articles", len(new_articles))
        logger.info("=" * 60)

        tier1_results: list[tuple[dict, dict]] = []
        tier1_map: dict[str, dict] = {}
        llm_candidates: list[dict] = []

        for i, article in enumerate(new_articles):
            rules_result = enrich_by_rules(article)
            tier1_results.append((article, rules_result))
            url_hash = article.get("url_hash", "")
            if url_hash:
                tier1_map[url_hash] = rules_result

            if rules_result["matchScore"] >= args.threshold:
                llm_candidates.append(article)

            if (i + 1) % 20 == 0 or (i + 1) == len(new_articles):
                logger.info(
                    "  Tier 1 progress: %d/%d scored (%d above threshold %d)",
                    i + 1, len(new_articles), len(llm_candidates), args.threshold,
                )

        logger.info(
            "Tier 1 complete: %d scored, %d above threshold %d → will send to LLM",
            len(new_articles), len(llm_candidates), args.threshold,
        )
        saved_pct = (
            (1 - len(llm_candidates) / len(new_articles)) * 100
            if new_articles else 0
        )
        logger.info(
            "LLM calls saved: %d (%.0f%% reduction)",
            len(new_articles) - len(llm_candidates), saved_pct,
        )

        if args.dry_run:
            logger.info("--- DRY RUN: Tier 1 scoring results ---")
            for article, rules in tier1_results:
                logger.info(
                    "  score=%3d imp=%-4s tier=%s  [%s] %s",
                    rules["matchScore"],
                    rules["importance"],
                    "LLM" if rules["matchScore"] >= args.threshold else "rules",
                    article.get("source_id", "?"),
                    article.get("title", "?")[:55],
                )
            return

        # ── Tier 2: LLM enrichment for high-score articles only ──
        llm_results_map: dict[str, dict] = {}
        if llm_candidates:
            if not settings.OPENROUTER_API_KEY:
                logger.warning(
                    "OPENROUTER_API_KEY not configured — skipping LLM, "
                    "using rules-only for all %d articles", len(new_articles),
                )
            else:
                logger.info("=" * 60)
                logger.info(
                    "TIER 2: LLM enrichment for %d articles (threshold >= %d)",
                    len(llm_candidates), args.threshold,
                )
                logger.info("=" * 60)

                llm_pairs = await process_articles_llm(
                    llm_candidates, tier1_map,
                )
                for article, llm_result in llm_pairs:
                    url_hash = article.get("url_hash", "")
                    if url_hash:
                        llm_results_map[url_hash] = llm_result

        # ── Merge: LLM overrides Tier 1 where available ──
        final_results: list[tuple[dict, dict]] = []
        for article, rules_result in tier1_results:
            url_hash = article.get("url_hash", "")
            if url_hash in llm_results_map:
                final = llm_results_map[url_hash]
            else:
                final = rules_result
            final_results.append((article, final))

        # Save enriched + update hashes
        new_hashes: set[str] = set()
        for article, enrichment in final_results:
            save_enriched(article, enrichment)
            h = article.get("url_hash", "")
            if h:
                new_hashes.add(h)

        all_hashes = processed_hashes | new_hashes
        save_processed_hashes(all_hashes)
        logger.info(
            "Saved %d enriched articles (%d via LLM, %d rules-only)",
            len(new_hashes), len(llm_results_map),
            len(new_hashes) - len(llm_results_map),
        )
    elif args.dry_run:
        logger.info("--- DRY RUN: no new articles to process ---")
        return
    else:
        logger.info("No new articles to process")

    # Rebuild output files from ALL enriched data
    all_enriched = load_all_enriched()
    logger.info("Total enriched articles for output: %d", len(all_enriched))
    rebuild_output_files(all_enriched)

    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
