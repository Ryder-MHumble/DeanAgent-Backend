from __future__ import annotations

from typing import Any

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
from app.crawlers.utils.http_client import fetch_json


class GitHubTalentSourceCrawler(BaseCrawler):
    async def fetch_and_parse(self) -> list[CrawledItem]:
        adapter_key = str(self.config.get("adapter_key") or "")
        if adapter_key == "github_users":
            return await self._fetch_users()
        if adapter_key == "github_contributors":
            return await self._fetch_contributors()

        try:
            payload = await fetch_json(self._source_url(), **fetch_options(self.config))
        except Exception as exc:
            if self.config.get("fallback_mode") == "evidence_only":
                return [
                    build_blocked_item(
                        self.config,
                        notes=str(exc),
                        signal_type="github_contributor",
                    )
                ]
            raise

        items = self._records_to_items(extract_records(payload))
        if items:
            return items
        if self.config.get("fallback_mode") == "evidence_only":
            return [
                build_review_item(
                    self.config,
                    notes="no structured github contributor records",
                    signal_type="github_contributor",
                )
            ]
        return []

    async def _fetch_users(self) -> list[CrawledItem]:
        try:
            payload = await fetch_json(
                self._source_url(),
                params={
                    "q": str(self.config.get("search_query") or "machine learning"),
                    "per_page": str(int(self.config.get("max_results", 10))),
                },
                headers={"Accept": "application/vnd.github+json"},
                **fetch_options(self.config),
            )
        except Exception as exc:
            return [
                build_blocked_item(
                    self.config,
                    notes=str(exc),
                    signal_type="github_contributor",
                )
            ]

        records = [
            {
                "candidate_name": item.get("login"),
                "github_login": item.get("login"),
                "followers": item.get("score"),
                "evidence_url": item.get("html_url"),
                "confidence": 0.65,
            }
            for item in payload.get("items", [])
            if isinstance(item, dict)
        ]
        return self._records_or_review(records)

    async def _fetch_contributors(self) -> list[CrawledItem]:
        records: list[dict[str, Any]] = []
        repo_seeds = self.config.get("repo_seeds") or []
        if not repo_seeds:
            try:
                payload = await fetch_json(self._source_url(), **fetch_options(self.config))
            except Exception as exc:
                return [
                    build_blocked_item(
                        self.config,
                        notes=str(exc),
                        signal_type="github_contributor",
                    )
                ]
            return self._records_or_review(extract_records(payload))

        for repo_full_name in repo_seeds[: int(self.config.get("max_repos", 3))]:
            url = f"https://api.github.com/repos/{repo_full_name}/contributors"
            try:
                contributors = await fetch_json(
                    url,
                    params={"per_page": str(int(self.config.get("max_results_per_repo", 8)))},
                    headers={"Accept": "application/vnd.github+json"},
                    **fetch_options(self.config),
                )
            except Exception:
                continue
            if not isinstance(contributors, list):
                continue
            for contributor in contributors:
                if not isinstance(contributor, dict):
                    continue
                records.append(
                    {
                        "candidate_name": contributor.get("login"),
                        "github_login": contributor.get("login"),
                        "repo_full_name": repo_full_name,
                        "contributions": contributor.get("contributions"),
                        "evidence_url": contributor.get("html_url"),
                        "confidence": 0.75,
                    }
                )
        return self._records_or_review(records)

    def _records_or_review(self, records: list[dict[str, Any]]) -> list[CrawledItem]:
        items = self._records_to_items(records)
        if items:
            return items
        return [
            build_review_item(
                self.config,
                notes="no github contributor records",
                signal_type="github_contributor",
            )
        ]

    def _records_to_items(self, records: list[dict[str, Any]]) -> list[CrawledItem]:
        items: list[CrawledItem] = []
        for record in records:
            item = self._record_to_item(record)
            if item is not None:
                items.append(item)
        return items

    def _record_to_item(self, record: dict[str, Any]) -> CrawledItem | None:
        candidate_name = self._clean(record.get("candidate_name"))
        evidence_url = self._clean(record.get("evidence_url")) or self._source_url()
        if not candidate_name or not evidence_url:
            return None

        github_login = self._clean(record.get("github_login"))
        repo_full_name = self._clean(record.get("repo_full_name"))
        company = self._clean(record.get("company"))
        blog = self._clean(record.get("blog"))

        talent_signal = build_talent_signal(
            signal_type="github_contributor",
            record_status="structured",
            evidence_url=evidence_url,
            candidate_name=candidate_name,
            track=get_track(self.config),
            confidence=float(record.get("confidence", 0.92)),
            identity_hints={
                key: value
                for key, value in {
                    "github_login": github_login,
                    "company": company,
                    "blog": blog,
                }.items()
                if value
            },
            source_metrics={
                key: value
                for key, value in {
                    "contributions": record.get("contributions"),
                    "followers": record.get("followers"),
                }.items()
                if value is not None
            },
            evidence_title=(
                repo_full_name
                or github_login
                or self.config.get("name")
                or self.source_id
            ),
            notes=self._clean(record.get("notes")),
        )

        return build_crawled_item(
            self.config,
            title=candidate_name,
            url=evidence_url,
            talent_signal=talent_signal,
            extra={
                "github_login": github_login,
                "repo_full_name": repo_full_name,
                "contributions": record.get("contributions"),
                "followers": record.get("followers"),
                "company": company,
                "blog": blog,
            },
        )

    def _source_url(self) -> str:
        seed_urls = self.config.get("seed_urls") or []
        return seed_urls[0] if seed_urls else str(self.config.get("url") or "")

    @staticmethod
    def _clean(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()
