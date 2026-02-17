"""Shared utilities for intel modules — keyword scoring, regex extraction, JSON I/O."""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import Any

from app.config import BASE_DIR

logger = logging.getLogger(__name__)

PROCESSED_BASE = BASE_DIR / "data" / "processed"

_EMPTY_RESPONSE: dict[str, Any] = {"generated_at": None, "item_count": 0, "items": []}

# ---------------------------------------------------------------------------
# Generic keyword scoring
# ---------------------------------------------------------------------------


def keyword_score(text: str, keywords: list[tuple[str, int]]) -> int:
    """Scan *text* for keyword matches and accumulate weights.

    Returns raw (unclamped) score.  Caller should ``min(100, max(0, score))``.
    """
    lower = text.lower()
    score = 0
    for kw, weight in keywords:
        if kw.lower() in lower:
            score += weight
    return score


def clamp_score(score: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, score))


# ---------------------------------------------------------------------------
# Generic importance computation
# ---------------------------------------------------------------------------


def compute_importance(
    match_score: int,
    deadline: str | None,
    title: str,
    *,
    high_keywords: list[str] | None = None,
) -> str:
    """Determine importance level: 紧急 / 重要 / 关注 / 一般.

    *high_keywords*: title keywords that trigger "重要" (default: AI-related).
    """
    if high_keywords is None:
        high_keywords = ["人工智能", "AI", "中关村", "大模型"]

    days_left: int | None = None
    if deadline:
        try:
            dl = datetime.strptime(deadline, "%Y-%m-%d").date()
            days_left = (dl - date.today()).days
        except ValueError:
            pass

    if days_left is not None and 0 < days_left <= 14:
        return "紧急"
    if match_score >= 70:
        return "重要"
    if any(kw in title for kw in high_keywords):
        return "重要"
    if match_score >= 40:
        return "关注"
    return "一般"


# ---------------------------------------------------------------------------
# Regex extraction helpers
# ---------------------------------------------------------------------------

FUNDING_PATTERNS = [
    re.compile(
        r"(?:不超过|最高|最多|上限)?\s*(\d+(?:\.\d+)?(?:\s*[-~至到]\s*\d+(?:\.\d+)?)?)\s*万(?:元)?",
    ),
    re.compile(r"(\d+(?:\.\d+)?)\s*亿(?:元)?"),
]

DEADLINE_PATTERNS = [
    re.compile(
        r"截止[日时]?[期间]?[为：:\s]*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    ),
    re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*[前止]"),
    re.compile(r"截止[日时]?[期间]?[为：:\s]*(\d{4})[/-](\d{1,2})[/-](\d{1,2})"),
]

_TITLES = (
    "总理|副总理|部长|副部长|主任|副主任|书记|副书记"
    "|院长|副院长|局长|副局长|委员|主席|副主席"
    "|市长|副市长|区长|副区长|司长|副司长"
)

LEADER_NAME_RE = re.compile(
    rf"(?:{_TITLES})\s*([\u4e00-\u9fa5]{{2,4}})"
    rf"|([\u4e00-\u9fa5]{{2,4}})\s*(?:{_TITLES})",
)


def extract_funding(text: str) -> str | None:
    """Extract funding amount from text using regex."""
    for pattern in FUNDING_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(0)
    return None


def extract_deadline(text: str) -> str | None:
    """Extract deadline date from text.  Returns YYYY-MM-DD or None."""
    for pattern in DEADLINE_PATTERNS:
        m = pattern.search(text)
        if m:
            groups = m.groups()
            try:
                year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                return date(year, month, day).isoformat()
            except (ValueError, IndexError):
                continue
    return None


def extract_leader(text: str) -> str | None:
    """Extract leader name from text near title/position keywords."""
    m = LEADER_NAME_RE.search(text)
    if m:
        return m.group(1) or m.group(2)
    return None


def compute_days_left(deadline: str | None) -> int | None:
    """Compute days from today to *deadline* (YYYY-MM-DD).  None if no deadline."""
    if not deadline:
        return None
    try:
        dl = datetime.strptime(deadline, "%Y-%m-%d").date()
        return max(0, (dl - date.today()).days)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# JSON I/O for processed intel data
# ---------------------------------------------------------------------------


def load_intel_json(module: str, filename: str) -> dict[str, Any]:
    """Load ``data/processed/{module}/{filename}``, returning empty response on failure."""
    path = PROCESSED_BASE / module / filename
    if not path.exists():
        return dict(_EMPTY_RESPONSE)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load %s: %s", path, e)
        return dict(_EMPTY_RESPONSE)


def get_intel_stats(*modules_and_files: tuple[str, str]) -> dict[str, Any]:
    """Read metadata (item_count, generated_at) from multiple processed files.

    Usage::

        get_intel_stats(("policy_intel", "feed.json"), ("policy_intel", "opportunities.json"))
    """
    stats: dict[str, Any] = {}
    for module, filename in modules_and_files:
        data = load_intel_json(module, filename)
        key = f"{module}_{filename.replace('.json', '')}"
        stats[key] = {
            "item_count": data.get("item_count", 0),
            "generated_at": data.get("generated_at"),
        }
    return stats
