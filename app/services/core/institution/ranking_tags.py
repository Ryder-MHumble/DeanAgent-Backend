"""Ranking and policy tag helpers for institution records."""

from __future__ import annotations

from typing import Any

QS_RANK_BANDS = ("前30", "前50", "前100", "前200", "200外")

_QS_BAND_ALIASES = {
    "前30": "前30",
    "top30": "前30",
    "top 30": "前30",
    "qs前30": "前30",
    "qs 前30": "前30",
    "前50": "前50",
    "top50": "前50",
    "top 50": "前50",
    "qs前50": "前50",
    "qs 前50": "前50",
    "前100": "前100",
    "top100": "前100",
    "top 100": "前100",
    "qs前100": "前100",
    "qs 前100": "前100",
    "前200": "前200",
    "top200": "前200",
    "top 200": "前200",
    "qs前200": "前200",
    "qs 前200": "前200",
    "200外": "200外",
    "200以外": "200外",
    "前200外": "200外",
    "qs200外": "200外",
    "qs 200外": "200外",
}


def derive_qs_rank_band(qs_rank: Any) -> str | None:
    """Derive the display QS rank band from a concrete rank."""
    if qs_rank is None:
        return None
    try:
        rank = int(qs_rank)
    except (TypeError, ValueError):
        return None
    if rank <= 0:
        return None
    if rank <= 30:
        return "前30"
    if rank <= 50:
        return "前50"
    if rank <= 100:
        return "前100"
    if rank <= 200:
        return "前200"
    return "200外"


def normalize_qs_rank_band(value: Any) -> str | None:
    """Normalize accepted QS band labels and common aliases."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.lower().replace("-", "").replace("_", "").strip()
    normalized = " ".join(normalized.split())
    return _QS_BAND_ALIASES.get(normalized)


def resolve_qs_rank_band(record: dict[str, Any]) -> str | None:
    """Resolve QS band from stored band first, then concrete rank."""
    return normalize_qs_rank_band(record.get("qs_rank_band")) or derive_qs_rank_band(
        record.get("qs_rank")
    )


def build_institution_tags(record: dict[str, Any]) -> list[str]:
    """Build ordered display tags for institution API responses."""
    tags: list[str] = []
    if record.get("is_985"):
        tags.append("985")
    if record.get("is_211"):
        tags.append("211")
    if record.get("is_double_first_class"):
        tags.append("双一流")
    qs_band = resolve_qs_rank_band(record)
    if qs_band:
        tags.append(f"QS {qs_band}")
    return tags
