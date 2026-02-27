"""Shared utilities for intel modules — keyword scoring, regex extraction, JSON I/O."""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
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


# ---------------------------------------------------------------------------
# Article date / datetime utilities
# ---------------------------------------------------------------------------

# Gov-site URL date patterns (for policy articles where published_at is missing)
_GOV_URL_DATE_RE1 = re.compile(r"/t(\d{4})(\d{2})(\d{2})_")
_GOV_URL_DATE_RE2 = re.compile(r"/(\d{4})(\d{2})/t\d+")


def article_date(article: dict, *, url_fallback: bool = False) -> str:
    """Extract YYYY-MM-DD date string from article.

    *url_fallback*: if True, attempt to parse date from gov-site URL patterns
    when published_at is unavailable (used by policy processor).
    """
    pub = article.get("published_at")
    if pub:
        try:
            return datetime.fromisoformat(pub).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass
    if url_fallback:
        url = article.get("url", "")
        m = _GOV_URL_DATE_RE1.search(url)
        if m:
            return f"{m[1]}-{m[2]}-{m[3]}"
        m = _GOV_URL_DATE_RE2.search(url)
        if m:
            return f"{m[1]}-{m[2]}-01"
    return date.today().isoformat()


def article_datetime(article: dict) -> datetime:
    """Extract datetime from article, fallback to now(UTC)."""
    pub = article.get("published_at")
    if pub:
        try:
            return datetime.fromisoformat(pub)
        except (ValueError, TypeError):
            pass
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def deduplicate_articles(articles: list[dict]) -> list[dict]:
    """Deduplicate articles by url_hash, keeping first occurrence."""
    seen: set[str] = set()
    unique: list[dict] = []
    for a in articles:
        h = a.get("url_hash", "")
        if h and h not in seen:
            seen.add(h)
            unique.append(a)
    return unique


# ---------------------------------------------------------------------------
# LLM response helpers
# ---------------------------------------------------------------------------


def clamp_value(value: Any, lo: int, hi: int, default: int) -> int:
    """Clamp a numeric value to [lo, hi], returning *default* if invalid type."""
    try:
        v = int(value)
        return max(lo, min(hi, v))
    except (TypeError, ValueError):
        return default


def str_or_none(value: Any) -> str | None:
    """Normalize value to a non-empty string or None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("null", "none", ""):
        return None
    return s


def parse_date_str(s: str | None) -> str | None:
    """Try to parse a date string in various formats to YYYY-MM-DD."""
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Source filtering
# ---------------------------------------------------------------------------


def resolve_source_ids_by_names(names: list[str]) -> set[str]:
    """根据信源名称（模糊匹配）解析出信源 ID 集合。

    Args:
        names: 待匹配的名称列表

    Returns:
        匹配到的信源 ID 集合
    """
    # 避免循环导入，在函数内部导入
    import asyncio
    from app.services.source_service import list_sources

    # 同步调用异步函数获取所有信源
    all_sources = asyncio.run(list_sources())
    matched_ids = set()

    for name_pattern in names:
        pattern_lower = name_pattern.lower().replace(' ', '')
        for source in all_sources:
            source_name_lower = source['name'].lower().replace(' ', '')
            if pattern_lower in source_name_lower:
                matched_ids.add(source['id'])

    return matched_ids


def parse_source_filter(
    source_id: str | None,
    source_ids: str | None,
    source_name: str | None,
    source_names: str | None,
) -> set[str] | None:
    """解析信源筛选参数，返回信源 ID 集合。

    Args:
        source_id: 单个信源 ID（精确）
        source_ids: 多个信源 ID，逗号分隔（精确）
        source_name: 单个信源名称（模糊）
        source_names: 多个信源名称，逗号分隔（模糊）

    Returns:
        None: 不筛选（返回所有信源）
        set[str]: 信源 ID 集合（已去重）
    """
    if not any([source_id, source_ids, source_name, source_names]):
        return None

    result = set()

    # 处理 ID（精确匹配）
    if source_id and source_id.strip():
        result.add(source_id.strip())
    if source_ids:
        for s in source_ids.split(','):
            if s.strip():
                result.add(s.strip())

    # 处理 name（模糊匹配）
    if source_name or source_names:
        names = []
        if source_name and source_name.strip():
            names.append(source_name.strip())
        if source_names:
            for s in source_names.split(','):
                if s.strip():
                    names.append(s.strip())

        if names:
            resolved_ids = resolve_source_ids_by_names(names)
            result.update(resolved_ids)

    return result if result else set()
