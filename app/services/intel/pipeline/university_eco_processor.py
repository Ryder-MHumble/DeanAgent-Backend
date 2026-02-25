"""University ecosystem processing pipeline — callable from orchestrator.

Reads raw university articles, classifies research outputs via keyword rules,
and generates processed JSON files for the frontend API.

Output:
  data/processed/university_eco/
    overview.json         — dashboard stats
    feed.json             — all articles as feed items
    research_outputs.json — articles categorized as 论文/专利/获奖
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from app.config import BASE_DIR
from app.services.intel.university_eco.rules import classify_article
from app.services.json_reader import get_articles

logger = logging.getLogger(__name__)

DIMENSION = "universities"
PROCESSED_DIR = BASE_DIR / "data" / "processed" / "university_eco"
HASHES_FILE = PROCESSED_DIR / "_processed_hashes.json"

GROUP_NAMES: dict[str, str] = {
    "university_news": "高校新闻",
    "ai_institutes": "AI研究院",
    "provincial": "省级教育",
    "awards": "奖项荣誉",
    "aggregators": "教育媒体",
}


# ---------------------------------------------------------------------------
# Hash tracking (incremental processing)
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
            {
                "hashes": sorted(hashes),
                "last_run": datetime.now(timezone.utc).isoformat(),
            },
            f, ensure_ascii=False, indent=2,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _article_date(article: dict) -> str:
    pub = article.get("published_at")
    if pub:
        try:
            return datetime.fromisoformat(pub).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass
    return date.today().isoformat()


def _is_today(article: dict) -> bool:
    return _article_date(article) == date.today().isoformat()


# ---------------------------------------------------------------------------
# Data quality filter — reject pagination artifacts and junk entries
# ---------------------------------------------------------------------------

_PAGINATION_RE = re.compile(r"^\d{1,4}$")
_JUNK_TITLES = frozenset({
    "上页", "下页", "首页", "尾页", "末页",
    "上一页", "下一页", "...", "…",
})


def _is_valid_article(article: dict) -> bool:
    """Filter out pagination artifacts and junk entries."""
    title = (article.get("title") or "").strip()

    if len(title) < 4:
        return False

    if title in _JUNK_TITLES:
        return False

    if _PAGINATION_RE.match(title):
        return False

    url = article.get("url", "")
    if not url or not url.startswith("http"):
        return False

    return True


def _first_image(article: dict) -> str | None:
    extra = article.get("extra") or {}
    images = extra.get("images") or []
    if images:
        img = images[0]
        if isinstance(img, dict):
            return img.get("src")
        if isinstance(img, str):
            return img
    return None


def _build_feed_item(article: dict) -> dict:
    extra = article.get("extra") or {}
    raw_images = extra.get("images") or []
    images = [
        {"src": img.get("src", ""), "alt": img.get("alt")}
        for img in raw_images
        if isinstance(img, dict) and img.get("src")
    ]
    return {
        "id": article.get("url_hash", ""),
        "title": article.get("title", ""),
        "url": article.get("url", ""),
        "published_at": article.get("published_at"),
        "source_id": article.get("source_id", ""),
        "source_name": article.get("source_name", ""),
        "group": article.get("group"),
        "tags": article.get("tags", []),
        "has_content": bool(article.get("content")),
        "thumbnail": _first_image(article),
        "is_new": article.get("is_new", False),
        "content": article.get("content"),
        "images": images,
    }


def _build_research_output(article: dict, enrichment: dict) -> dict:
    extra = article.get("extra") or {}
    raw_images = extra.get("images") or []
    images = [
        {"src": img.get("src", ""), "alt": img.get("alt")}
        for img in raw_images
        if isinstance(img, dict) and img.get("src")
    ]
    return {
        "id": article.get("url_hash", ""),
        "title": article.get("title", ""),
        "url": article.get("url", ""),
        "date": _article_date(article),
        "source_id": article.get("source_id", ""),
        "source_name": article.get("source_name", ""),
        "group": article.get("group"),
        "institution": enrichment["institution"],
        "type": enrichment["type"],
        "influence": enrichment["influence"],
        "field": enrichment["field"],
        "authors": enrichment["authors"],
        "aiAnalysis": enrichment["aiAnalysis"],
        "detail": enrichment["detail"],
        "matchScore": enrichment["matchScore"],
        "content": article.get("content"),
        "images": images,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def process_university_eco_pipeline(
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Run university ecosystem processing pipeline.

    Generates overview.json, feed.json, and research_outputs.json
    under data/processed/university_eco/.

    Returns summary dict for the pipeline orchestrator.
    """
    articles = get_articles(DIMENSION)
    logger.info("University eco pipeline: loaded %d articles", len(articles))

    # Deduplicate by url_hash
    seen: set[str] = set()
    unique: list[dict] = []
    for a in articles:
        h = a.get("url_hash", "")
        if h and h not in seen:
            seen.add(h)
            unique.append(a)

    # Filter out junk / pagination artifacts
    valid = [a for a in unique if _is_valid_article(a)]
    logger.info(
        "University eco pipeline: filtered %d -> %d valid articles",
        len(unique), len(valid),
    )

    # Incremental hash tracking
    processed_hashes = set() if force else _load_processed_hashes()
    new_articles = [
        a for a in valid if a.get("url_hash", "") not in processed_hashes
    ]

    logger.info(
        "University eco pipeline: %d unique, %d valid, %d new (previously: %d)",
        len(unique), len(valid), len(new_articles), len(processed_hashes),
    )

    # Track new hashes
    new_count = 0
    if new_articles:
        for article in new_articles:
            h = article.get("url_hash", "")
            if h:
                processed_hashes.add(h)
                new_count += 1
        _save_processed_hashes(processed_hashes)

    # ── Build outputs from ALL valid articles ─────────────────────────
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Feed items
    feed_items: list[dict] = []
    for article in valid:
        feed_items.append(_build_feed_item(article))
    feed_items.sort(
        key=lambda x: x.get("published_at") or "1970-01-01", reverse=True,
    )

    # 2. Research outputs (classified articles)
    research_outputs: list[dict] = []
    for article in valid:
        enrichment = classify_article(article)
        if enrichment:
            research_outputs.append(_build_research_output(article, enrichment))
    research_outputs.sort(key=lambda x: x.get("date", ""), reverse=True)

    # 3. Overview stats
    group_stats: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "new_today": 0, "sources": set()},
    )
    new_today_total = 0
    for article in valid:
        grp = article.get("group") or "unknown"
        entry = group_stats[grp]
        entry["total"] += 1
        entry["sources"].add(article.get("source_id", ""))
        if _is_today(article):
            entry["new_today"] += 1
            new_today_total += 1

    groups_list = []
    for grp, stats in sorted(group_stats.items()):
        groups_list.append({
            "group": grp,
            "group_name": GROUP_NAMES.get(grp, grp),
            "total_articles": stats["total"],
            "new_today": stats["new_today"],
            "source_count": len(stats["sources"]),
        })

    # Research type stats
    type_counts = defaultdict(int)
    for ro in research_outputs:
        type_counts[ro["type"]] += 1

    overview = {
        "generated_at": now_iso,
        "total_articles": len(unique),
        "new_today": new_today_total,
        "active_source_count": len({a.get("source_id") for a in valid}),
        "groups": groups_list,
        "research_outputs_count": len(research_outputs),
        "research_type_stats": {
            "论文": type_counts.get("论文", 0),
            "专利": type_counts.get("专利", 0),
            "获奖": type_counts.get("获奖", 0),
        },
    }

    # ── Write output files ────────────────────────────────────────────────

    overview_path = PROCESSED_DIR / "overview.json"
    with open(overview_path, "w", encoding="utf-8") as f:
        json.dump(overview, f, ensure_ascii=False, indent=2)

    feed_path = PROCESSED_DIR / "feed.json"
    with open(feed_path, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": now_iso, "item_count": len(feed_items),
             "items": feed_items},
            f, ensure_ascii=False, indent=2,
        )

    research_path = PROCESSED_DIR / "research_outputs.json"
    with open(research_path, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": now_iso, "item_count": len(research_outputs),
             "items": research_outputs},
            f, ensure_ascii=False, indent=2,
        )

    logger.info(
        "University eco output: %d feed, %d research (论文=%d 专利=%d 获奖=%d)",
        len(feed_items), len(research_outputs),
        type_counts.get("论文", 0),
        type_counts.get("专利", 0),
        type_counts.get("获奖", 0),
    )

    return {
        "total_articles": len(articles),
        "unique": len(valid),
        "new_processed": new_count,
        "feed_items": len(feed_items),
        "research_outputs": len(research_outputs),
        "research_papers": type_counts.get("论文", 0),
        "research_patents": type_counts.get("专利", 0),
        "research_awards": type_counts.get("获奖", 0),
    }
