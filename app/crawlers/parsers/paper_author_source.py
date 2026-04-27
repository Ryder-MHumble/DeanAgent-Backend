from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
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
from app.config import BASE_DIR


class PaperAuthorSourceCrawler(BaseCrawler):
    async def fetch_and_parse(self) -> list[CrawledItem]:
        adapter_key = str(self.config.get("adapter_key") or "")
        if adapter_key == "semantic_scholar":
            return await self._fetch_semantic_scholar()
        if adapter_key == "dblp_json":
            return await self._fetch_dblp()
        if adapter_key == "arxiv_atom":
            return await self._fetch_arxiv()
        if adapter_key == "openreview_notes":
            return await self._fetch_openreview()
        if adapter_key == "author_aggregate_json":
            return await self._fetch_author_aggregate()

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

    async def _fetch_openreview(self) -> list[CrawledItem]:
        try:
            payload = await fetch_json(
                self._openreview_api_url(),
                params=self._openreview_params(),
                **fetch_options(self.config),
            )
        except Exception as exc:
            return [build_blocked_item(self.config, notes=str(exc), signal_type="paper_author")]

        return self._records_or_review(self._openreview_notes_to_records(payload))

    async def _fetch_author_aggregate(self) -> list[CrawledItem]:
        raw_path = self.config.get("local_results_path")
        if raw_path not in ("", None):
            data_path = self._resolve_local_results_path(raw_path)
            if data_path is None:
                return [
                    build_blocked_item(
                        self.config,
                        notes="local_results_path is required for author_aggregate_json",
                        signal_type="paper_author",
                    )
                ]
            try:
                payload = json.loads(data_path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                return [
                    build_blocked_item(
                        self.config,
                        notes=str(exc),
                        signal_type="paper_author",
                    )
                ]
            return self._records_or_review(self._author_aggregate_to_records(payload))

        try:
            payload = await fetch_json(self._source_url(), **fetch_options(self.config))
        except Exception as exc:
            return [build_blocked_item(self.config, notes=str(exc), signal_type="paper_author")]

        return self._records_or_review(self._author_aggregate_to_records(payload))

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
        notes = self._clean(record.get("notes"))
        affiliations = self._clean_list(record.get("affiliations"))
        papers = self._dict_list(record.get("papers"))

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
                    "openreview_author_id": self._clean(record.get("openreview_author_id")),
                    "author_order": record.get("author_order"),
                }.items()
                if value not in ("", None)
            },
            source_metrics={
                key: value
                for key, value in {
                    "paper_count_in_scope": record.get("paper_count_in_scope"),
                    "citation_count": record.get("citation_count"),
                    "h_index": record.get("h_index"),
                }.items()
                if value is not None
            },
            evidence_title=(
                self._clean(record.get("evidence_title"))
                or paper_title
                or venue
                or self.config.get("name")
                or self.source_id
            ),
            notes=notes,
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
                "h_index": record.get("h_index"),
                "dblp_pid": self._clean(record.get("dblp_pid")),
                "openreview_note_id": self._clean(record.get("openreview_note_id")),
                "openreview_forum_id": self._clean(record.get("openreview_forum_id")),
                "affiliations": affiliations,
                "papers": papers,
                "notes": notes,
            },
        )

    def _author_aggregate_to_records(self, payload: Any) -> list[dict[str, Any]]:
        authors: list[Any] = []
        source_name = ""
        if isinstance(payload, dict):
            source_name = self._clean(payload.get("source"))
            if isinstance(payload.get("authors"), list):
                authors = payload.get("authors", [])
            elif isinstance(payload.get("results"), dict):
                nested_authors = payload["results"].get("authors")
                if isinstance(nested_authors, list):
                    authors = nested_authors
        elif isinstance(payload, list):
            authors = payload

        records: list[dict[str, Any]] = []
        for author in authors:
            if not isinstance(author, dict):
                continue
            papers = self._dict_list(author.get("papers"))
            first_paper = papers[0] if papers else {}
            affiliations = self._clean_list(author.get("affiliations"))
            paper_count_in_scope = author.get("total_papers")
            if paper_count_in_scope is None:
                paper_count_in_scope = len(papers)
            records.append(
                {
                    "candidate_name": author.get("candidate_name") or author.get("name"),
                    "university": self._clean(author.get("university")) or (
                        affiliations[0] if affiliations else ""
                    ),
                    "paper_title": first_paper.get("title") or author.get("paper_title"),
                    "venue": first_paper.get("venue") or author.get("venue"),
                    "venue_year": first_paper.get("year") or author.get("venue_year"),
                    "paper_count_in_scope": paper_count_in_scope,
                    "citation_count": author.get("total_citations") or author.get("citation_count"),
                    "h_index": author.get("h_index"),
                    "affiliations": affiliations,
                    "papers": papers,
                    "evidence_url": self._clean(author.get("evidence_url")) or self._source_url(),
                    "confidence": 0.8,
                    "notes": (
                        f"aggregated author profile from {source_name}" if source_name else ""
                    ),
                }
            )
        return records

    def _openreview_notes_to_records(self, payload: Any) -> list[dict[str, Any]]:
        notes = payload.get("notes") if isinstance(payload, dict) else []
        if not isinstance(notes, list):
            return []

        records: list[dict[str, Any]] = []
        for note in notes:
            if not isinstance(note, dict):
                continue
            content = note.get("content") if isinstance(note.get("content"), dict) else {}
            authors = self._clean_list(self._openreview_value(content.get("authors")))
            authorids = self._clean_list(self._openreview_value(content.get("authorids")))
            title = self._clean(self._openreview_value(content.get("title")))
            venue = self._clean(self._openreview_value(content.get("venue"))) or self._clean(
                note.get("domain")
            )
            venue_year = self._extract_year(
                venue,
                self._clean(note.get("domain")),
                self._clean(note.get("invitation")),
            )
            forum_id = self._clean(note.get("forum") or note.get("id"))
            evidence_url = (
                f"https://openreview.net/forum?id={forum_id}" if forum_id else self._source_url()
            )
            for index, author in enumerate(authors[:3], start=1):
                records.append(
                    {
                        "candidate_name": author,
                        "paper_title": title,
                        "venue": venue,
                        "venue_year": venue_year,
                        "author_order": index,
                        "evidence_url": evidence_url,
                        "openreview_author_id": (
                            authorids[index - 1] if len(authorids) >= index else ""
                        ),
                        "openreview_note_id": self._clean(note.get("id")),
                        "openreview_forum_id": self._clean(note.get("forum")),
                        "confidence": 0.78,
                    }
                )
        return records

    def _openreview_api_url(self) -> str:
        source_url = self._source_url()
        parsed = urlparse(source_url)
        if parsed.netloc in {"api.openreview.net", "api2.openreview.net"} and parsed.path:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return str(self.config.get("api_url") or "https://api2.openreview.net/notes")

    def _openreview_params(self) -> dict[str, str]:
        source_url = self._source_url()
        parsed = urlparse(source_url)
        query = parse_qs(parsed.query)

        invitation = self._clean(
            self.config.get("openreview_invitation")
            or self.config.get("invitation")
            or self._query_value(query, "invitation")
        )
        if not invitation:
            group_id = self._clean(
                self.config.get("openreview_group_id")
                or self.config.get("group_id")
                or self._query_value(query, "id")
            )
            if group_id:
                suffix = self._clean(self.config.get("invitation_suffix")) or "-/Submission"
                invitation = f"{group_id.rstrip('/')}/{suffix.lstrip('/')}"

        params: dict[str, str] = {
            "limit": str(int(self.config.get("max_results", self._query_value(query, "limit") or 10))),
        }
        if invitation:
            params["invitation"] = invitation

        content_venue = self._clean(
            self.config.get("content_venue") or self._query_value(query, "content.venue")
        )
        if content_venue:
            params["content.venue"] = content_venue

        forum_id = self._clean(self.config.get("forum") or self._query_value(query, "forum"))
        if forum_id:
            params["forum"] = forum_id

        return params

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
    def _dict_list(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    @staticmethod
    def _clean_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [cleaned for item in value if (cleaned := str(item).strip())]

    @staticmethod
    def _openreview_value(value: Any) -> Any:
        if isinstance(value, dict) and "value" in value:
            return value.get("value")
        return value

    @staticmethod
    def _extract_year(*values: Any) -> int | None:
        for value in values:
            if not value:
                continue
            match = re.search(r"(19|20)\d{2}", str(value))
            if match:
                return int(match.group(0))
        return None

    @staticmethod
    def _query_value(query: dict[str, list[str]], key: str) -> str:
        values = query.get(key) or []
        return values[0] if values else ""

    @staticmethod
    def _resolve_local_results_path(raw_path: Any) -> Path | None:
        if raw_path in ("", None):
            return None
        path = Path(str(raw_path))
        if not path.is_absolute():
            path = BASE_DIR / path
        return path if path.exists() else None

    @staticmethod
    def _clean(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()
