"""Filtering helpers for university ecosystem articles."""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from app.scheduler.manager import load_all_source_configs


def _normalize_domain(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    host = (urlparse(candidate).hostname or "").strip().lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _domain_matches(host: str, allowed_domains: set[str]) -> bool:
    for domain in allowed_domains:
        if host == domain or host.endswith(f".{domain}"):
            return True
    return False


@lru_cache(maxsize=1)
def _allowed_domains_by_source() -> dict[str, set[str]]:
    domain_map: dict[str, set[str]] = {}
    for config in load_all_source_configs():
        if config.get("dimension") != "universities":
            continue

        allowed: set[str] = set()
        for field in ("url", "base_url"):
            domain = _normalize_domain(config.get(field))
            if domain:
                allowed.add(domain)

        for domain in config.get("allowed_domains", []) or []:
            normalized = _normalize_domain(domain)
            if normalized:
                allowed.add(normalized)

        if allowed:
            domain_map[config.get("id", "")] = allowed

    return domain_map


def is_allowed_university_article(article: dict) -> bool:
    """Keep only articles whose URL matches the configured source domain."""
    source_id = article.get("source_id", "")
    url = article.get("url", "")

    if not source_id or not url:
        return False

    host = _normalize_domain(url)
    if not host:
        return False

    allowed = _allowed_domains_by_source().get(source_id)
    if not allowed:
        return True

    return _domain_matches(host, allowed)


def filter_university_articles(articles: list[dict]) -> list[dict]:
    return [article for article in articles if is_allowed_university_article(article)]


def dedupe_university_articles(articles: list[dict]) -> list[dict]:
    """Deduplicate articles while preserving order."""
    seen: set[tuple] = set()
    deduped: list[dict] = []

    for article in articles:
        key = None
        if article.get("url_hash"):
            key = ("url_hash", article["url_hash"])
        elif article.get("url"):
            key = ("url", article["url"])
        else:
            key = (
                "fallback",
                article.get("source_id"),
                article.get("title"),
                article.get("published_at"),
            )

        if key in seen:
            continue
        seen.add(key)
        deduped.append(article)

    return deduped
