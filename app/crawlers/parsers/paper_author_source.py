from __future__ import annotations

from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree

from app.crawlers.base import BaseCrawler, CrawledItem
from app.crawlers.parsers._talent_scout_common import (
    build_blocked_item,
    build_crawled_item,
    build_review_item,
    build_talent_signal,
    extract_records,
    fetch_options,
    get_track,
)
from app.crawlers.utils.http_client import fetch_json, fetch_page


class PaperAuthorSourceCrawler(BaseCrawler):
    async def fetch_and_parse(self) -> list[CrawledItem]:
        adapter_key = str(self.config.get("adapter_key") or "")
        if adapter_key == "semantic_scholar":
            return await self._fetch_semantic_scholar()
        if adapter_key == "dblp_json":
            return await self._fetch_dblp()
        if adapter_key == "arxiv_atom":
            return await self._fetch_arxiv()

        try:
            payload = await fetch_json(self._source_url(), **fetch_options(self.config))
        except Exception as exc:
            if self.config.get("fallback_mode") == "evidence_only":
                return [
                    build_blocked_item(
                        self.config,
                        notes=str(exc),
                        signal_type="paper_author",
                    )
                ]
            raise

        items = [self._record_to_item(record) for record in extract_records(payload)]
        items = [item for item in items if item is not None]
        if items:
            return items
        if self.config.get("fallback_mode") == "evidence_only":
            return [
                build_review_item(
                    self.config,
                    notes="no structured paper author records",
                    signal_type="paper_author",
                )
            ]
        return []

    async def _fetch_semantic_scholar(self) -> list[CrawledItem]:
        try:
            payload = await fetch_json(
                self._source_url(),
                params={
                    "query": str(self.config.get("search_query") or "artificial intelligence"),
                    "limit": str(int(self.config.get("max_results", 10))),
                    "fields": "title,authors,year,url,citationCount,venue",
                },
                **fetch_options(self.config),
            )
        except Exception as exc:
            return [build_blocked_item(self.config, notes=str(exc), signal_type="paper_author")]

        records: list[dict[str, Any]] = []
        for paper in payload.get("data", []):
            if not isinstance(paper, dict):
                continue
            authors = paper.get("authors") if isinstance(paper.get("authors"), list) else []
            for index, author in enumerate(authors[:3], start=1):
                if not isinstance(author, dict):
                    continue
                records.append(
                    {
                        "candidate_name": author.get("name"),
                        "paper_title": paper.get("title"),
                        "venue": paper.get("venue"),
                        "venue_year": paper.get("year"),
                        "author_order": index,
                        "citation_count": paper.get("citationCount"),
                        "evidence_url": paper.get("url"),
                        "confidence": 0.75,
                    }
                )
        return self._records_or_review(records)

    async def _fetch_dblp(self) -> list[CrawledItem]:
        try:
            payload = await fetch_json(
                self._source_url(),
                params={
                    "q": str(self.config.get("search_query") or "machine learning"),
                    "format": "json",
                    "h": str(int(self.config.get("max_results", 10))),
                },
                **fetch_options(self.config),
            )
        except Exception as exc:
            return [build_blocked_item(self.config, notes=str(exc), signal_type="paper_author")]

        hits = (
            payload.get("result", {})
            .get("hits", {})
            .get("hit", [])
        )
        records: list[dict[str, Any]] = []
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            info = hit.get("info") if isinstance(hit.get("info"), dict) else {}
            authors = info.get("authors", {}).get("author", [])
            if isinstance(authors, dict):
                authors = [authors]
            for index, author in enumerate(authors[:3], start=1):
                name = author.get("text") if isinstance(author, dict) else str(author)
                records.append(
                    {
                        "candidate_name": name,
                        "paper_title": info.get("title"),
                        "venue": info.get("venue"),
                        "venue_year": info.get("year"),
                        "author_order": index,
                        "dblp_pid": author.get("@pid") if isinstance(author, dict) else "",
                        "evidence_url": info.get("url"),
                        "confidence": 0.8,
                    }
                )
        return self._records_or_review(records)

    async def _fetch_arxiv(self) -> list[CrawledItem]:
        query = urlencode(
            {
                "search_query": str(self.config.get("search_query") or "cat:cs.AI"),
                "start": "0",
                "max_results": str(int(self.config.get("max_results", 10))),
            }
        )
        url = f"{self._source_url()}?{query}"
        try:
            raw = await fetch_page(url, **fetch_options(self.config))
        except Exception as exc:
            return [build_blocked_item(self.config, notes=str(exc), signal_type="paper_author")]

        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        root = ElementTree.fromstring(raw)
        records: list[dict[str, Any]] = []
        for entry in root.findall("atom:entry", namespace):
            title = self._node_text(entry, "atom:title", namespace)
            year = self._node_text(entry, "atom:published", namespace)[:4]
            evidence_url = self._node_text(entry, "atom:id", namespace)
            for index, author in enumerate(entry.findall("atom:author", namespace)[:3], start=1):
                records.append(
                    {
                        "candidate_name": self._node_text(author, "atom:name", namespace),
                        "paper_title": title,
                        "venue": "arXiv",
                        "venue_year": year,
                        "author_order": index,
                        "evidence_url": evidence_url,
                        "confidence": 0.7,
                    }
                )
        return self._records_or_review(records)

    def _records_or_review(self, records: list[dict[str, Any]]) -> list[CrawledItem]:
        items = [self._record_to_item(record) for record in records]
        items = [item for item in items if item is not None]
        if items:
            return items
        return [
            build_review_item(
                self.config,
                notes="no paper author records",
                signal_type="paper_author",
            )
        ]

    def _record_to_item(self, record: dict[str, Any]) -> CrawledItem | None:
        candidate_name = self._clean(record.get("candidate_name"))
        evidence_url = self._clean(record.get("evidence_url")) or self._source_url()
        if not candidate_name or not evidence_url:
            return None

        university = self._clean(record.get("university"))
        department = self._clean(record.get("department"))
        email = self._clean(record.get("email"))
        paper_title = self._clean(record.get("paper_title"))
        venue = self._clean(record.get("venue"))

        talent_signal = build_talent_signal(
            signal_type="paper_author",
            record_status="structured",
            evidence_url=evidence_url,
            candidate_name=candidate_name,
            university=university,
            department=department,
            email=email,
            track=get_track(self.config),
            confidence=float(record.get("confidence", 0.95)),
            identity_hints={
                key: value
                for key, value in {
                    "dblp_pid": self._clean(record.get("dblp_pid")),
                    "author_order": record.get("author_order"),
                }.items()
                if value not in ("", None)
            },
            source_metrics={
                key: value
                for key, value in {
                    "paper_count_in_scope": record.get("paper_count_in_scope"),
                    "citation_count": record.get("citation_count"),
                }.items()
                if value is not None
            },
            evidence_title=paper_title or venue or self.config.get("name") or self.source_id,
            notes=self._clean(record.get("notes")),
        )

        return build_crawled_item(
            self.config,
            title=candidate_name,
            url=evidence_url,
            talent_signal=talent_signal,
            extra={
                "paper_title": paper_title,
                "venue": venue,
                "venue_year": record.get("venue_year"),
                "author_order": record.get("author_order"),
                "paper_count_in_scope": record.get("paper_count_in_scope"),
                "citation_count": record.get("citation_count"),
                "dblp_pid": self._clean(record.get("dblp_pid")),
            },
        )

    @staticmethod
    def _node_text(node: ElementTree.Element, path: str, namespace: dict[str, str]) -> str:
        found = node.find(path, namespace)
        if found is None or found.text is None:
            return ""
        return found.text.strip()

    def _source_url(self) -> str:
        seed_urls = self.config.get("seed_urls") or []
        return seed_urls[0] if seed_urls else str(self.config.get("url") or "")

    @staticmethod
    def _clean(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()
