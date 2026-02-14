"""Business logic for Talent Radar module."""
from __future__ import annotations

import hashlib
import logging
from datetime import date

from app.schemas.business.talent import TalentEntry, TalentListResponse
from app.services.json_reader import get_articles

logger = logging.getLogger(__name__)


def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def get_talent_list(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
) -> TalentListResponse:
    """Get talent-related articles from talent dimension."""
    articles = get_articles("talent", date_from=date_from, date_to=date_to)

    items: list[TalentEntry] = []
    for art in articles[:limit]:
        items.append(TalentEntry(
            id=_make_id(art.get("url", "")),
            title=art.get("title", ""),
            url=art.get("url", ""),
            institution=art.get("source_name", ""),
            source_id=art.get("source_id", ""),
            source_name=art.get("source_name", ""),
            date=art.get("published_at"),
            tags=art.get("tags", []),
        ))

    return TalentListResponse(items=items, total=len(items))
