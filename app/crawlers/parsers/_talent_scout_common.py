from __future__ import annotations

from typing import Any

from app.crawlers.base import CrawledItem

_SIGNAL_TYPE_BY_ENTITY_FAMILY = {
    "competition": "competition",
    "paper_author": "paper_author",
    "github_talent": "github_contributor",
}

_ALLOWED_RECORD_STATUSES = {"structured", "partial", "needs_review", "blocked"}


def get_signal_type(entity_family: str) -> str:
    signal_type = _SIGNAL_TYPE_BY_ENTITY_FAMILY.get(entity_family)
    if not signal_type:
        raise ValueError(f"Unsupported entity_family for talent scout: {entity_family}")
    return signal_type


def get_track(config: dict[str, Any]) -> str:
    track = config.get("track")
    if isinstance(track, str) and track.strip():
        return track.strip()

    tracks = config.get("tracks")
    if isinstance(tracks, list):
        for value in tracks:
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def build_talent_signal(
    *,
    signal_type: str,
    record_status: str,
    evidence_url: str,
    candidate_name: str = "",
    university: str = "",
    department: str = "",
    email: str = "",
    track: str = "",
    confidence: float = 0.0,
    identity_hints: dict[str, Any] | None = None,
    source_metrics: dict[str, Any] | None = None,
    evidence_title: str = "",
    notes: str = "",
) -> dict[str, Any]:
    if signal_type not in set(_SIGNAL_TYPE_BY_ENTITY_FAMILY.values()):
        raise ValueError(f"Unsupported talent signal type: {signal_type}")
    if record_status not in _ALLOWED_RECORD_STATUSES:
        raise ValueError(f"Unsupported record_status: {record_status}")
    if not evidence_url:
        raise ValueError("evidence_url is required for talent_signal")

    return {
        "signal_type": signal_type,
        "candidate_name": candidate_name,
        "university": university,
        "department": department,
        "email": email,
        "track": track,
        "record_status": record_status,
        "confidence": confidence,
        "identity_hints": identity_hints or {},
        "source_metrics": source_metrics or {},
        "evidence_title": evidence_title,
        "evidence_url": evidence_url,
        "notes": notes,
    }


def build_crawled_item(
    config: dict[str, Any],
    *,
    title: str,
    url: str,
    talent_signal: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> CrawledItem:
    item_extra = dict(extra or {})
    item_extra["talent_signal"] = talent_signal

    return CrawledItem(
        title=title,
        url=url,
        source_id=config["id"],
        dimension=config.get("dimension"),
        extra=item_extra,
    )


def build_blocked_item(
    config: dict[str, Any],
    *,
    notes: str = "",
    signal_type: str | None = None,
) -> CrawledItem:
    entity_family = config.get("entity_family", "")
    resolved_signal_type = signal_type or get_signal_type(entity_family)
    evidence_url = _get_seed_url(config)
    evidence_title = config.get("name") or config["id"]

    talent_signal = build_talent_signal(
        signal_type=resolved_signal_type,
        record_status="blocked",
        evidence_url=evidence_url,
        track=get_track(config),
        confidence=0.0,
        evidence_title=evidence_title,
        notes=notes,
    )

    return build_crawled_item(
        config,
        title=evidence_title,
        url=evidence_url,
        talent_signal=talent_signal,
    )


def build_review_item(
    config: dict[str, Any],
    *,
    notes: str = "",
    signal_type: str | None = None,
) -> CrawledItem:
    entity_family = config.get("entity_family", "")
    resolved_signal_type = signal_type or get_signal_type(entity_family)
    evidence_url = _get_seed_url(config)
    evidence_title = config.get("name") or config["id"]

    talent_signal = build_talent_signal(
        signal_type=resolved_signal_type,
        record_status="needs_review",
        evidence_url=evidence_url,
        track=get_track(config),
        confidence=0.1,
        evidence_title=evidence_title,
        notes=notes,
    )

    return build_crawled_item(
        config,
        title=evidence_title,
        url=evidence_url,
        talent_signal=talent_signal,
    )


def fetch_options(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "timeout": float(config.get("request_timeout", 8.0)),
        "max_retries": int(config.get("max_retries", 1)),
        "request_delay": float(config.get("request_delay", 0.1)),
    }


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]

    if not isinstance(payload, dict):
        return []

    for key in ("data", "items", "records", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [record for record in value if isinstance(record, dict)]

    return []


def _get_seed_url(config: dict[str, Any]) -> str:
    seed_urls = config.get("seed_urls")
    if isinstance(seed_urls, list):
        for value in seed_urls:
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, dict):
                url = value.get("url")
                if isinstance(url, str) and url.strip():
                    return url.strip()
    return ""
