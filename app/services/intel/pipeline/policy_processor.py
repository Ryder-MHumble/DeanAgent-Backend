"""Policy processing pipeline — callable from orchestrator.

Reuses service-layer functions (rules engine, json_reader) directly.
Self-contained hash tracking and output logic (no imports from scripts/).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any

from app.config import BASE_DIR, settings
from app.services.intel.policy.rules import enrich_by_rules
from app.services.json_reader import get_articles

logger = logging.getLogger(__name__)

DIMENSIONS = ["national_policy", "beijing_policy"]
PROCESSED_DIR = BASE_DIR / "data" / "processed" / "policy_intel"
ENRICHED_DIR = PROCESSED_DIR / "_enriched"
HASHES_FILE = PROCESSED_DIR / "_processed_hashes.json"


# ---------------------------------------------------------------------------
# Hash tracking
# ---------------------------------------------------------------------------

def _load_processed_hashes() -> set[str]:
    if not HASHES_FILE.exists():
        return set()
    try:
        with open(HASHES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("hashes", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _save_processed_hashes(hashes: set[str]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with open(HASHES_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"hashes": sorted(hashes),
             "last_run": datetime.now(timezone.utc).isoformat()},
            f, ensure_ascii=False, indent=2,
        )


# ---------------------------------------------------------------------------
# Enriched cache I/O
# ---------------------------------------------------------------------------

def _save_enriched(article: dict, enrichment: dict) -> None:
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
        "llm": enrichment,
    }
    path = ENRICHED_DIR / f"{url_hash}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def _load_all_enriched() -> list[tuple[dict, dict]]:
    if not ENRICHED_DIR.exists():
        return []
    results: list[tuple[dict, dict]] = []
    for path in ENRICHED_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            results.append((data["article"], data["llm"]))
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning("Skipping invalid enriched file %s: %s", path.name, e)
    return results


# ---------------------------------------------------------------------------
# Output builders (mirrors scripts/process_policy_intel.py)
# ---------------------------------------------------------------------------

def _article_date(article: dict) -> str:
    pub = article.get("published_at")
    if pub:
        try:
            return datetime.fromisoformat(pub).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass
    url = article.get("url", "")
    m = re.search(r'/t(\d{4})(\d{2})(\d{2})_', url)
    if m:
        return f"{m[1]}-{m[2]}-{m[3]}"
    m = re.search(r'/(\d{4})(\d{2})/t\d+', url)
    if m:
        return f"{m[1]}-{m[2]}-01"
    return date.today().isoformat()


def _determine_category(article: dict, llm_result: dict) -> str:
    if llm_result.get("isOpportunity"):
        return "政策机会"
    dim = article.get("dimension", "")
    if dim == "beijing_policy":
        return "北京政策"
    if dim == "national_policy":
        return "国家政策"
    return "一般"


def _determine_agency_type(article: dict) -> str:
    dim = article.get("dimension", "")
    if dim == "national_policy":
        return "national"
    if dim == "beijing_policy":
        return "beijing"
    return "ministry"


def _compute_status(days_left: int | None) -> str:
    if days_left is None:
        return "tracking"
    if days_left <= 7:
        return "urgent"
    if days_left <= 30:
        return "active"
    return "tracking"


def _build_feed_item(article: dict, llm: dict) -> dict:
    category = _determine_category(article, llm)
    original_tags = article.get("tags", [])
    llm_tags = llm.get("tags", [])
    merged_tags = list(dict.fromkeys(original_tags + llm_tags))
    return {
        "id": article.get("url_hash", ""),
        "title": article.get("title", ""),
        "summary": llm.get("summary", ""),
        "category": category,
        "importance": llm.get("importance", "一般"),
        "date": _article_date(article),
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


def _build_opportunity_item(article: dict, llm: dict) -> dict | None:
    if not llm.get("isOpportunity"):
        return None
    days_left = llm.get("daysLeft")
    return {
        "id": article.get("url_hash", ""),
        "name": article.get("title", ""),
        "agency": llm.get("agency", article.get("source_name", "")),
        "agencyType": _determine_agency_type(article),
        "matchScore": llm.get("matchScore", 0),
        "funding": llm.get("funding") or "待确认",
        "deadline": llm.get("deadline") or "待确认",
        "daysLeft": days_left if days_left is not None else 999,
        "status": _compute_status(days_left),
        "aiInsight": llm.get("aiInsight", ""),
        "detail": llm.get("detail", ""),
        "sourceUrl": article.get("url", ""),
    }


def _rebuild_output_files(all_enriched: list[tuple[dict, dict]]) -> tuple[int, int]:
    """Regenerate feed.json and opportunities.json. Returns (feed_count, opp_count)."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()

    feed_items: list[dict] = []
    opportunity_items: list[dict] = []
    for article, llm in all_enriched:
        feed_items.append(_build_feed_item(article, llm))
        opp = _build_opportunity_item(article, llm)
        if opp:
            opportunity_items.append(opp)

    feed_items.sort(key=lambda x: x.get("date", ""), reverse=True)
    opportunity_items.sort(key=lambda x: x.get("daysLeft", 999))

    feed_path = PROCESSED_DIR / "feed.json"
    with open(feed_path, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": now_iso, "item_count": len(feed_items), "items": feed_items},
            f, ensure_ascii=False, indent=2,
        )

    opp_path = PROCESSED_DIR / "opportunities.json"
    with open(opp_path, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": now_iso, "item_count": len(opportunity_items),
             "items": opportunity_items},
            f, ensure_ascii=False, indent=2,
        )

    logger.info(
        "Policy output: %d feed items, %d opportunities",
        len(feed_items), len(opportunity_items),
    )
    return len(feed_items), len(opportunity_items)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def process_policy_pipeline(
    *,
    force: bool = False,
    threshold: int = 40,
) -> dict[str, Any]:
    """Run policy processing pipeline (Tier 1 rules only).

    Returns summary dict for the pipeline orchestrator.
    """
    # Load raw articles from all relevant dimensions
    all_articles: list[dict] = []
    for dim in DIMENSIONS:
        articles = get_articles(dim)
        logger.info("Policy pipeline: loaded %d articles from %s", len(articles), dim)
        all_articles.extend(articles)

    # Exclude personnel-related groups (belong in personnel pipeline)
    all_articles = [
        a for a in all_articles
        if not (a.get("dimension") == "beijing_policy" and a.get("group") == "news_personnel")
    ]

    # Deduplicate by url_hash
    seen: set[str] = set()
    unique_articles: list[dict] = []
    for a in all_articles:
        h = a.get("url_hash", "")
        if h and h not in seen:
            seen.add(h)
            unique_articles.append(a)

    # Filter already-processed (incremental)
    processed_hashes = set() if force else _load_processed_hashes()
    new_articles = [
        a for a in unique_articles if a.get("url_hash", "") not in processed_hashes
    ]

    logger.info(
        "Policy pipeline: %d unique, %d new (previously processed: %d)",
        len(unique_articles), len(new_articles), len(processed_hashes),
    )

    # Tier 1: Rule-based scoring for new articles
    new_hashes: set[str] = set()
    if new_articles:
        for article in new_articles:
            rules_result = enrich_by_rules(article)
            _save_enriched(article, rules_result)
            h = article.get("url_hash", "")
            if h:
                new_hashes.add(h)

        all_hashes = processed_hashes | new_hashes
        _save_processed_hashes(all_hashes)
        logger.info("Policy pipeline: scored %d new articles", len(new_hashes))

    # Rebuild output files from ALL enriched data (excluding personnel)
    all_enriched = [
        (a, llm) for a, llm in _load_all_enriched()
        if a.get("dimension") not in ("personnel",)
        and not (a.get("dimension") == "beijing_policy" and a.get("group") == "news_personnel")
    ]
    feed_count, opp_count = _rebuild_output_files(all_enriched)

    return {
        "total_raw": len(all_articles),
        "unique": len(unique_articles),
        "new_processed": len(new_hashes),
        "previously_processed": len(processed_hashes),
        "total_enriched": len(all_enriched),
        "feed_items": feed_count,
        "opportunities": opp_count,
    }


async def process_policy_llm_enrichment(
    *,
    threshold: int | None = None,
    concurrency: int = 3,
) -> dict[str, Any]:
    """Tier 2: LLM enrichment for high-scoring policy articles.

    Reads existing rule-based results from _enriched/ directory, filters those
    not yet LLM-enriched and above threshold, calls enrich_article_lite(), and
    rebuilds output files.

    Returns summary dict for the pipeline orchestrator.
    """
    from app.services.intel.policy.llm import LLMError, enrich_article_lite

    if threshold is None:
        threshold = settings.LLM_THRESHOLD

    all_enriched = _load_all_enriched()
    if not all_enriched:
        return {"skipped": True, "reason": "no enriched articles to process"}

    # Filter: not yet LLM-enriched AND matchScore >= threshold
    candidates: list[tuple[dict, dict]] = []
    already_llm = 0
    below_threshold = 0
    for article, llm_data in all_enriched:
        if llm_data.get("enrichment_tier") == "llm":
            already_llm += 1
            continue
        if llm_data.get("matchScore", 0) < threshold:
            below_threshold += 1
            continue
        candidates.append((article, llm_data))

    logger.info(
        "Policy LLM enrichment: %d candidates (already_llm=%d, below_threshold=%d)",
        len(candidates), already_llm, below_threshold,
    )

    if not candidates:
        return {
            "llm_enriched": 0,
            "already_llm": already_llm,
            "below_threshold": below_threshold,
            "total": len(all_enriched),
        }

    # Run LLM enrichment with concurrency control
    sem = asyncio.Semaphore(concurrency)
    llm_count = 0
    errors = 0

    async def _enrich_one(article: dict, tier1: dict) -> bool:
        nonlocal llm_count, errors
        async with sem:
            try:
                result = await enrich_article_lite(article, tier1)
                _save_enriched(article, result)
                llm_count += 1
                return True
            except LLMError as e:
                errors += 1
                logger.warning(
                    "LLM failed for %s: %s",
                    article.get("title", "?")[:40], e,
                )
                return False

    tasks = [_enrich_one(a, t) for a, t in candidates]
    await asyncio.gather(*tasks)

    # Rebuild output files with updated enrichments
    if llm_count > 0:
        all_enriched = _load_all_enriched()
        _rebuild_output_files(all_enriched)

    return {
        "llm_enriched": llm_count,
        "llm_errors": errors,
        "already_llm": already_llm,
        "below_threshold": below_threshold,
        "total": len(all_enriched),
    }
