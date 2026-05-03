from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse

import httpx
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config import settings  # noqa: E402
from app.db.pool import close_pool, get_pool, init_pool  # noqa: E402

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
OPENREVIEW_API2 = "https://api2.openreview.net"
OPENREVIEW_API1 = "https://api.openreview.net"
ARXIV_API_URL = "https://export.arxiv.org/api/query"
ACADEMIC_MONITOR_BASE_URL = os.environ.get(
    "ACADEMIC_MONITOR_API_URL", "http://127.0.0.1:8000"
).rstrip("/")
ACADEMIC_MONITOR_ENRICH_PAPER_PATH = "/api/identity/enrich-paper"
ACADEMIC_MONITOR_TIMEOUT = float(os.environ.get("ACADEMIC_MONITOR_TIMEOUT", "60"))

_ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([^?#/\"'<\s]+)", re.I)
_ARXIV_DOI_RE = re.compile(r"10\.48550/arxiv\.([^?#\s]+)", re.I)
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_META_TAG_RE = re.compile(r"<meta\s+(?P<attrs>[^>]+)>", re.I)
_HTML_ATTR_RE = re.compile(r"(?P<key>[\w:.-]+)\s*=\s*(?P<value>\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
_CVF_ABSTRACT_RE = re.compile(r"<div\s+[^>]*id=[\"']abstract[\"'][^>]*>(?P<abstract>.*?)</div>", re.I | re.S)
_CLASS_ABSTRACT_RE = re.compile(
    r"<(?P<tag>div|p|section)\s+[^>]*class=[\"'][^\"']*(?:paper-abstract|acl-abstract|abstract)[^\"']*[\"'][^>]*>"
    r"(?P<abstract>.*?)</(?P=tag)>",
    re.I | re.S,
)
_IJCAI_ABSTRACT_RE = re.compile(
    r"<hr>\s*<div\s+class=[\"']row[\"'][^>]*>.*?<div\s+class=[\"']col-md-12[\"'][^>]*>"
    r"(?P<abstract>.*?)</div>\s*<div\s+class=[\"']col-md-12[\"'][^>]*>\s*<div\s+class=[\"']keywords",
    re.I | re.S,
)
_NON_WORD_RE = re.compile(r"[^a-z0-9]+")
_STUDENT_RE = re.compile(
    r"\b(phd|doctoral|master|msc|undergrad|undergraduate|bachelor|student|candidate)\b|"
    r"博士|硕士|研究生|本科生",
    re.IGNORECASE,
)
_NON_STUDENT_RE = re.compile(
    r"\b(professor|faculty|lecturer|scientist|engineer|director|pi|chair|fellow)\b|"
    r"教授|讲师|研究员|工程师|院士",
    re.IGNORECASE,
)
_CHINA_COUNTRIES = {"cn", "china", "pr china", "p.r. china", "中国", "中华人民共和国"}
_CHINESE_ORG_HINTS = (
    "China",
    "Chinese",
    "Tsinghua",
    "Peking University",
    "Zhejiang University",
    "Fudan University",
    "Shanghai Jiao Tong",
    "University of Science and Technology of China",
    "中国",
    "清华",
    "北大",
    "浙江大学",
    "复旦",
    "上海交通",
    "中国科学院",
)
PDF_AFFILIATION_SOURCE_IDS = {"cvpr", "eccv", "neurips", "acl_long", "acl_short", "ijcai"}
_AFFILIATION_LINE_RE = re.compile(
    r"\b(university|institute|college|school|laboratory|lab\.?|centre|center|research|"
    r"academy|hospital|corporation|inc\.?|ltd\.?|company|department)\b|"
    r"大学|学院|研究院|研究所|实验室|中心",
    re.I,
)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_PDF_PREFIX_MARK_RE = re.compile(r"^\s*(?:[\d*†‡§¶#]+|[♠♣♡♥♦▲△□■]+)\s*")
_PDF_PAPER_SECTION_RE = re.compile(r"\babstract\b|\bintroduction\b", re.I)


@dataclass(slots=True)
class ParsedUrlIds:
    openreview_id: str | None = None
    arxiv_id: str | None = None
    doi: str | None = None


class AsyncRateLimiter:
    def __init__(self, qps: float | None):
        self.min_interval = 0.0 if not qps or qps <= 0 else 1.0 / qps
        self._lock = asyncio.Lock()
        self._last_call_at = 0.0

    async def wait(self) -> None:
        if self.min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait_for = self.min_interval - (now - self._last_call_at)
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            self._last_call_at = time.monotonic()


@dataclass(slots=True)
class EnrichmentResult:
    source_hits: list[str] = field(default_factory=list)
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    authors: list[str] = field(default_factory=list)
    affiliations: list[dict[str, Any]] = field(default_factory=list)
    author_descriptions: list[dict[str, Any]] = field(default_factory=list)
    author_experiences: list[dict[str, Any]] = field(default_factory=list)
    profile_flags: list[dict[str, Any]] = field(default_factory=list)
    openreview_authorids: list[str] = field(default_factory=list)

    def as_update(self) -> dict[str, Any]:
        return {
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "abstract": self.abstract,
            "authors": self.authors,
            "affiliations": self.affiliations,
            "author_descriptions": self.author_descriptions,
            "author_experiences": self.author_experiences,
            "profile_flags": self.profile_flags,
        }


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_doi(value: Any) -> str | None:
    text = clean_text(value).lower()
    if not text:
        return None
    text = text.replace("https://doi.org/", "").replace("http://doi.org/", "")
    text = text.replace("doi:", "").strip()
    return text or None


def normalize_arxiv_id(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    doi_match = _ARXIV_DOI_RE.search(text)
    if doi_match:
        return doi_match.group(1)
    text = text.removeprefix("arXiv:").removeprefix("arxiv:")
    text = text.removesuffix(".pdf")
    return text or None


def title_key(value: Any) -> str:
    return _NON_WORD_RE.sub(" ", clean_text(value).lower()).strip()


def parse_json_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def read_paper_id_file(path: Path) -> list[str]:
    paper_ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        token = line.strip()
        if not token or token.startswith("#"):
            continue
        paper_ids.append(token)
    return paper_ids


def parse_url_ids(*urls: str | None) -> ParsedUrlIds:
    result = ParsedUrlIds()
    for raw_url in urls:
        url = clean_text(raw_url)
        if not url:
            continue
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "openreview.net" in parsed.netloc:
            note_id = (qs.get("id") or [""])[0].strip()
            if note_id:
                result.openreview_id = note_id
        if "arxiv.org" in parsed.netloc:
            match = _ARXIV_RE.search(url)
            if match:
                result.arxiv_id = normalize_arxiv_id(match.group(1))
        if "doi.org" in parsed.netloc:
            match = _DOI_RE.search(url)
            if match:
                result.doi = normalize_doi(match.group(0))
    return result


def _clean_html_text(value: Any) -> str:
    return clean_text(unescape(_HTML_TAG_RE.sub(" ", str(value or ""))))


def _citation_author_name(value: str) -> str:
    text = clean_text(unescape(value))
    if "," not in text:
        return text
    family, given = [clean_text(part) for part in text.split(",", 1)]
    return clean_text(f"{given} {family}") or text


def iter_html_meta(raw_html: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for tag_match in _META_TAG_RE.finditer(raw_html):
        attrs = {
            attr_match.group("key").lower(): attr_match.group("value").strip("\"'")
            for attr_match in _HTML_ATTR_RE.finditer(tag_match.group("attrs"))
        }
        name = clean_text(attrs.get("name") or attrs.get("property")).lower()
        content = clean_text(unescape(attrs.get("content") or ""))
        if name and content:
            entries.append((name, content))
    return entries


def _best_abstract_from_html(raw_html: str, meta: list[tuple[str, str]]) -> str | None:
    for name, content in meta:
        if name in {"dc.description", "citation_abstract", "citation_abstract_text"}:
            return content
    for pattern in (_CVF_ABSTRACT_RE, _CLASS_ABSTRACT_RE, _IJCAI_ABSTRACT_RE):
        match = pattern.search(raw_html)
        if match:
            abstract = _clean_html_text(match.group("abstract"))
            if abstract:
                return abstract
    return None


def parse_academic_page_html(raw_html: str, *, source_hit: str) -> EnrichmentResult | None:
    result = EnrichmentResult(source_hits=[source_hit])
    meta = iter_html_meta(raw_html)
    last_author_index: int | None = None
    for name, content in meta:
        if name == "citation_author" and content:
            result.authors.append(_citation_author_name(content))
            last_author_index = len(result.authors)
        elif name == "dc.creator.personalname" and content:
            result.authors.append(content)
            last_author_index = len(result.authors)
        elif name == "citation_author_institution" and content and last_author_index:
            author_name = result.authors[last_author_index - 1] if len(result.authors) >= last_author_index else ""
            result.affiliations.append(
                {
                    "author_order": last_author_index,
                    "author_name": author_name,
                    "affiliation": content,
                }
            )
        elif name == "citation_doi" and content:
            result.doi = normalize_doi(content)
        elif name == "dc.identifier.doi" and content and not result.doi:
            result.doi = normalize_doi(content)

    result.abstract = _best_abstract_from_html(raw_html, meta)

    arxiv_match = _ARXIV_RE.search(raw_html)
    if arxiv_match:
        result.arxiv_id = normalize_arxiv_id(arxiv_match.group(1))
    doi_match = _DOI_RE.search(raw_html)
    if doi_match and not result.doi:
        result.doi = normalize_doi(doi_match.group(0))

    if result.abstract or result.arxiv_id or result.doi or result.authors:
        return result
    return None


def parse_cvf_openaccess_html(raw_html: str) -> EnrichmentResult | None:
    return parse_academic_page_html(raw_html, source_hit="cvf")


def pdf_url_from_academic_page(detail_url: str, raw_html: str) -> str | None:
    for name, content in iter_html_meta(raw_html):
        if name == "citation_pdf_url" and clean_text(content):
            return urljoin(detail_url, content)
    match = re.search(r"href=[\"'](?P<href>[^\"']+\.pdf)[\"']", raw_html, re.I)
    if not match:
        return None
    href = clean_text(match.group("href"))
    return urljoin(detail_url, href)


def is_cvf_openaccess_url(value: Any) -> bool:
    parsed = urlparse(clean_text(value))
    return parsed.netloc == "openaccess.thecvf.com" and parsed.path.endswith(".html")


def academic_page_source_hit(value: Any) -> str | None:
    parsed = urlparse(clean_text(value))
    if not parsed.scheme or not parsed.netloc:
        return None
    host = parsed.netloc.lower()
    if host == "openaccess.thecvf.com" and parsed.path.endswith(".html"):
        return "cvf"
    if host == "www.ecva.net" and parsed.path.endswith((".php", ".html")):
        return "ecva"
    if host == "papers.nips.cc" and parsed.path.endswith(".html"):
        return "neurips"
    if host == "aclanthology.org" and parsed.path.endswith("/"):
        return "acl"
    if host == "www.ijcai.org" and "/proceedings/" in parsed.path:
        return "ijcai"
    if host == "ojs.aaai.org" and "/article/view/" in parsed.path:
        return "aaai"
    return None


def decode_openalex_abstract(index: Any) -> str | None:
    if not isinstance(index, dict) or not index:
        return None
    positions: dict[int, str] = {}
    for word, raw_offsets in index.items():
        if not isinstance(raw_offsets, list):
            continue
        for offset in raw_offsets:
            if isinstance(offset, int):
                positions[offset] = str(word)
    if not positions:
        return None
    return " ".join(positions[i] for i in sorted(positions))


def affiliation_mappings_from_openalex(work: dict[str, Any]) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    for idx, authorship in enumerate(work.get("authorships") or [], start=1):
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author") if isinstance(authorship.get("author"), dict) else {}
        name = clean_text(authorship.get("raw_author_name") or author.get("display_name"))
        institutions = []
        for inst in authorship.get("institutions") or []:
            if not isinstance(inst, dict):
                continue
            display_name = clean_text(inst.get("display_name"))
            if display_name and display_name not in institutions:
                institutions.append(display_name)
        if name and institutions:
            mappings.append(
                {
                    "author_order": idx,
                    "author_name": name,
                    "affiliation": "; ".join(institutions),
                }
            )
    return mappings


def _affiliation_score(value: Any) -> tuple[int, int]:
    mappings = parse_json_list(value)
    non_empty = 0
    for item in mappings:
        if isinstance(item, dict) and clean_text(item.get("affiliation")):
            non_empty += 1
    return non_empty, len(mappings)


def _profile_list_score(value: Any) -> tuple[int, int]:
    items = parse_json_list(value)
    non_empty = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        meaningful = [
            item.get("description"),
            item.get("experiences"),
            item.get("profile_id"),
            item.get("profile_url"),
            item.get("is_chinese"),
            item.get("is_current_student"),
            item.get("evidence"),
        ]
        if any(value not in ("", None, [], {}) for value in meaningful):
            non_empty += 1
    return non_empty, len(items)


def _clean_dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in parse_json_list(value) if isinstance(item, dict)]


def merge_enrichment(row: dict[str, Any], enrichment: dict[str, Any]) -> dict[str, Any]:
    current_authors = [clean_text(v) for v in parse_json_list(row.get("authors")) if clean_text(v)]
    candidate_authors = [
        clean_text(v) for v in parse_json_list(enrichment.get("authors")) if clean_text(v)
    ]
    current_affiliations = parse_json_list(row.get("affiliations"))
    candidate_affiliations = [
        item
        for item in parse_json_list(enrichment.get("affiliations"))
        if isinstance(item, dict) and clean_text(item.get("author_name")) and clean_text(item.get("affiliation"))
    ]
    current_abstract = clean_text(row.get("abstract"))
    candidate_abstract = clean_text(enrichment.get("abstract"))
    current_author_descriptions = _clean_dict_list(row.get("author_descriptions"))
    candidate_author_descriptions = _clean_dict_list(enrichment.get("author_descriptions"))
    current_author_experiences = _clean_dict_list(row.get("author_experiences"))
    candidate_author_experiences = _clean_dict_list(enrichment.get("author_experiences"))
    current_profile_flags = _clean_dict_list(row.get("profile_flags"))
    candidate_profile_flags = _clean_dict_list(enrichment.get("profile_flags"))

    return {
        "doi": normalize_doi(row.get("doi")) or normalize_doi(enrichment.get("doi")),
        "arxiv_id": normalize_arxiv_id(row.get("arxiv_id"))
        or normalize_arxiv_id(enrichment.get("arxiv_id")),
        "abstract": (
            candidate_abstract
            if len(candidate_abstract) > len(current_abstract)
            else (current_abstract or None)
        ),
        "authors": candidate_authors if len(candidate_authors) > len(current_authors) else current_authors,
        "affiliations": (
            candidate_affiliations
            if _affiliation_score(candidate_affiliations) > _affiliation_score(current_affiliations)
            else current_affiliations
        ),
        "author_descriptions": (
            candidate_author_descriptions
            if _profile_list_score(candidate_author_descriptions)
            > _profile_list_score(current_author_descriptions)
            else current_author_descriptions
        ),
        "author_experiences": (
            candidate_author_experiences
            if _profile_list_score(candidate_author_experiences)
            > _profile_list_score(current_author_experiences)
            else current_author_experiences
        ),
        "profile_flags": (
            candidate_profile_flags
            if _profile_list_score(candidate_profile_flags) > _profile_list_score(current_profile_flags)
            else current_profile_flags
        ),
    }


def _openreview_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _extract_profile_affiliation(profile: dict[str, Any]) -> str | None:
    content = profile.get("content") if isinstance(profile.get("content"), dict) else {}
    candidates: list[str] = []
    for key in ("institution", "affiliation"):
        value = _openreview_value(content.get(key))
        if isinstance(value, dict):
            value = value.get("name") or value.get("display_name") or value.get("value")
        if clean_text(value):
            candidates.append(clean_text(value))
    history = _openreview_value(content.get("history"))
    if isinstance(history, list):
        for item in history:
            if not isinstance(item, dict):
                continue
            inst = _openreview_value(item.get("institution"))
            if isinstance(inst, dict):
                inst = inst.get("name") or inst.get("display_name") or inst.get("value")
            if clean_text(inst):
                candidates.append(clean_text(inst))
    return candidates[0] if candidates else None


def iter_profile_author_pairs(
    authors: list[str],
    authorids: list[str],
    *,
    max_profile_requests: int,
):
    limit = len(authorids) if max_profile_requests <= 0 else min(max_profile_requests, len(authorids))
    for idx, author_id in enumerate(authorids[:limit], start=1):
        author_id_clean = clean_text(author_id)
        if not author_id_clean.startswith("~"):
            continue
        author_name = clean_text(authors[idx - 1] if idx - 1 < len(authors) else "")
        yield idx, author_name, author_id_clean


def _profile_id(profile: dict[str, Any]) -> str | None:
    profile_id = clean_text(profile.get("id"))
    if profile_id:
        return profile_id
    content = profile.get("content") if isinstance(profile.get("content"), dict) else {}
    names = content.get("names") if isinstance(content.get("names"), list) else []
    for name in names:
        if isinstance(name, dict) and clean_text(name.get("username")):
            return clean_text(name.get("username"))
    return None


def _history_experience(item: dict[str, Any]) -> dict[str, Any]:
    inst = item.get("institution") if isinstance(item.get("institution"), dict) else {}
    return {
        "position": clean_text(item.get("position")) or None,
        "start": item.get("start"),
        "end": item.get("end"),
        "institution": clean_text(inst.get("name")) or None,
        "department": clean_text(inst.get("department")) or None,
        "domain": clean_text(inst.get("domain")) or None,
        "country": clean_text(inst.get("country")) or None,
    }


def _profile_is_chinese(experiences: list[dict[str, Any]]) -> bool | None:
    text = " ".join(
        clean_text(value)
        for exp in experiences
        for value in (
            exp.get("institution"),
            exp.get("department"),
            exp.get("domain"),
            exp.get("country"),
        )
        if value
    )
    countries = {clean_text(exp.get("country")).lower() for exp in experiences if exp.get("country")}
    if countries & _CHINA_COUNTRIES:
        return True
    if any(hint.lower() in text.lower() for hint in _CHINESE_ORG_HINTS):
        return True
    return None


def _profile_is_current_student(experiences: list[dict[str, Any]]) -> bool | None:
    current_positions = [
        clean_text(exp.get("position"))
        for exp in experiences
        if exp.get("end") in (None, "", "Present", "present")
    ]
    current_text = " ".join(current_positions)
    if _NON_STUDENT_RE.search(current_text):
        return False
    if _STUDENT_RE.search(current_text):
        return True
    return None


def enrichment_from_openreview_profile(
    profile: dict[str, Any],
    *,
    author_order: int,
    author_name: str,
) -> dict[str, dict[str, Any] | None]:
    content = profile.get("content") if isinstance(profile.get("content"), dict) else {}
    history = content.get("history") if isinstance(content.get("history"), list) else []
    experiences = [
        _history_experience(item)
        for item in history
        if isinstance(item, dict) and isinstance(item.get("institution"), dict)
    ]
    experiences = [
        {key: value for key, value in exp.items() if value not in ("", None)}
        for exp in experiences
    ]
    current = next(
        (
            exp
            for exp in experiences
            if exp.get("end") in (None, "", "Present", "present") or "end" not in exp
        ),
        experiences[0] if experiences else {},
    )
    affiliation = clean_text(current.get("institution"))
    description = ""
    if current:
        position = clean_text(current.get("position"))
        institution = clean_text(current.get("institution"))
        department = clean_text(current.get("department"))
        dates = "-".join(
            clean_text(value)
            for value in (current.get("start"), current.get("end") or "至今")
            if clean_text(value)
        )
        parts = [part for part in (dates, institution, department, position) if part]
        if parts:
            description = f"{author_name}: " + "，".join(parts)
    profile_id = _profile_id(profile)
    profile_url = f"https://openreview.net/profile?id={profile_id}" if profile_id else None
    return {
        "affiliation": (
            {"author_order": author_order, "author_name": author_name, "affiliation": affiliation}
            if affiliation
            else None
        ),
        "description": (
            {
                "author_order": author_order,
                "author_name": author_name,
                "description": description,
            }
            if description
            else None
        ),
        "experiences": (
            {
                "author_order": author_order,
                "author_name": author_name,
                "experiences": experiences,
            }
            if experiences
            else None
        ),
        "profile_flags": {
            "author_order": author_order,
            "author_name": author_name,
            "profile_id": profile_id,
            "profile_url": profile_url,
            "is_chinese": _profile_is_chinese(experiences),
            "is_current_student": _profile_is_current_student(experiences),
            "evidence": {"source": "openreview_profile_history"},
        },
    }


def academic_monitor_result_from_payload(payload: Any) -> EnrichmentResult | None:
    if not isinstance(payload, dict):
        return None
    raw_authors = payload.get("authors") or payload.get("items") or payload.get("results") or []
    if not isinstance(raw_authors, list):
        return None

    result = EnrichmentResult(source_hits=["academic_monitor"])
    for idx, item in enumerate(raw_authors, start=1):
        if not isinstance(item, dict):
            continue
        author_order = int(item.get("author_order") or item.get("order") or idx)
        author_name = clean_text(
            item.get("author_name") or item.get("name") or item.get("name_raw") or item.get("name_normalized")
        )
        if not author_name:
            continue

        description = clean_text(
            item.get("author_description") or item.get("description") or item.get("summary")
        )
        if description:
            result.author_descriptions.append(
                {
                    "author_order": author_order,
                    "author_name": author_name,
                    "description": description,
                }
            )

        experiences = item.get("author_experiences") or item.get("experiences") or []
        if isinstance(experiences, list) and experiences:
            result.author_experiences.append(
                {
                    "author_order": author_order,
                    "author_name": author_name,
                    "experiences": [exp for exp in experiences if isinstance(exp, dict)],
                }
            )

        raw_flags = item.get("profile_flags") if isinstance(item.get("profile_flags"), dict) else {}
        profile_flag = {
            "author_order": author_order,
            "author_name": author_name,
            **raw_flags,
        }
        for key in ("profile_id", "profile_url", "resolution", "evidence"):
            if item.get(key) not in ("", None, [], {}):
                profile_flag[key] = item.get(key)
        if any(
            profile_flag.get(key) not in ("", None, [], {})
            for key in (
                "profile_id",
                "profile_url",
                "is_chinese",
                "is_current_student",
                "resolution",
                "evidence",
            )
        ):
            result.profile_flags.append(profile_flag)

        institutions = item.get("institutions") or []
        if isinstance(institutions, str):
            institutions = [institutions]
        current_affiliation = clean_text(item.get("current_affiliation"))
        affiliation_parts = [clean_text(value) for value in institutions if clean_text(value)]
        if current_affiliation and current_affiliation not in affiliation_parts:
            affiliation_parts.insert(0, current_affiliation)
        if affiliation_parts:
            result.affiliations.append(
                {
                    "author_order": author_order,
                    "author_name": author_name,
                    "affiliation": "; ".join(dict.fromkeys(affiliation_parts)),
                }
            )

    return result if result.as_update() != EnrichmentResult(source_hits=[]).as_update() else None


async def fetch_author_enrichment_from_academic_monitor(
    client: httpx.AsyncClient,
    *,
    paper_id: str | None,
    forum_id: str | None,
    authors: list[str],
    authorids: list[str],
    existing_affiliations: list[dict[str, Any]],
) -> EnrichmentResult | None:
    if not ACADEMIC_MONITOR_BASE_URL or not authors:
        return None
    author_payload = []
    for index, author_name in enumerate(authors, start=1):
        entry: dict[str, Any] = {
            "author_order": index,
            "author_name": author_name,
        }
        if index - 1 < len(authorids) and clean_text(authorids[index - 1]):
            entry["profile_id"] = clean_text(authorids[index - 1])
        author_payload.append(entry)
    payload = {
        "paper_id": paper_id,
        "forum_id": forum_id,
        "authors": author_payload,
        "existing_affiliations": existing_affiliations,
    }
    try:
        response = await client.post(
            f"{ACADEMIC_MONITOR_BASE_URL}{ACADEMIC_MONITOR_ENRICH_PAPER_PATH}",
            json=payload,
            timeout=ACADEMIC_MONITOR_TIMEOUT,
        )
        response.raise_for_status()
    except Exception:
        return None
    return academic_monitor_result_from_payload(response.json())


async def fetch_openreview(
    client: httpx.AsyncClient,
    note_id: str,
    *,
    max_profile_requests: int,
    limiter: AsyncRateLimiter | None = None,
    profile_cache: dict[str, dict[str, Any] | None] | None = None,
) -> EnrichmentResult | None:
    note = None
    for api_host in (OPENREVIEW_API2, OPENREVIEW_API1):
        try:
            if limiter is not None:
                await limiter.wait()
            response = await client.get(f"{api_host}/notes", params={"id": note_id})
            response.raise_for_status()
            notes = response.json().get("notes") or []
            if notes:
                note = notes[0]
                break
        except Exception:
            continue
    if not isinstance(note, dict):
        return None

    content = note.get("content") if isinstance(note.get("content"), dict) else {}
    title = clean_text(_openreview_value(content.get("title")))
    authors = _openreview_value(content.get("authors")) or []
    authorids = _openreview_value(content.get("authorids")) or []
    if isinstance(authors, str):
        authors = [item.strip() for item in authors.split(",") if item.strip()]
    if isinstance(authorids, str):
        authorids = [item.strip() for item in authorids.split(",") if item.strip()]
    abstract = clean_text(_openreview_value(content.get("abstract"))) or None

    result = EnrichmentResult(source_hits=["openreview"])
    result.abstract = abstract
    result.authors = [clean_text(item) for item in authors if clean_text(item)]
    result.openreview_authorids = [clean_text(item) for item in authorids if clean_text(item)]
    for idx, name, author_id in iter_profile_author_pairs(
        authors,
        authorids,
        max_profile_requests=max_profile_requests,
    ):
        profile = profile_cache.get(author_id) if profile_cache is not None else None
        if profile is None and (profile_cache is None or author_id not in profile_cache):
            try:
                if limiter is not None:
                    await limiter.wait()
                response = await client.get(f"{OPENREVIEW_API2}/profiles", params={"id": author_id})
                response.raise_for_status()
                profiles = response.json().get("profiles") or []
                profile = profiles[0] if profiles else None
            except Exception:
                profile = None
            if profile_cache is not None:
                profile_cache[author_id] = profile
        if not profile:
            continue
        affiliation = _extract_profile_affiliation(profile)
        if name and affiliation:
            result.affiliations.append(
                {"author_order": idx, "author_name": name, "affiliation": affiliation}
            )
        if name:
            profile_enrichment = enrichment_from_openreview_profile(
                profile,
                author_order=idx,
                author_name=name,
            )
            description = profile_enrichment.get("description")
            experiences = profile_enrichment.get("experiences")
            profile_flags = profile_enrichment.get("profile_flags")
            if isinstance(description, dict):
                result_description = description
            else:
                result_description = None
            if isinstance(experiences, dict):
                result_experiences = experiences
            else:
                result_experiences = None
            if isinstance(profile_flags, dict):
                result_profile_flags = profile_flags
            else:
                result_profile_flags = None
            if result_description:
                result.author_descriptions.append(result_description)
            if result_experiences:
                result.author_experiences.append(result_experiences)
            if result_profile_flags:
                result.profile_flags.append(result_profile_flags)
    if title:
        return result
    return result if result.authors or result.affiliations or result.abstract else None


async def fetch_arxiv_by_id(client: httpx.AsyncClient, arxiv_id: str) -> EnrichmentResult | None:
    try:
        response = await client.get(ARXIV_API_URL, params={"id_list": arxiv_id})
        response.raise_for_status()
    except Exception:
        return None
    return _parse_arxiv_feed(response.text)


async def fetch_arxiv_by_title(client: httpx.AsyncClient, title: str) -> EnrichmentResult | None:
    query = f'ti:"{title}"'
    try:
        response = await client.get(
            ARXIV_API_URL,
            params={"search_query": query, "max_results": "3", "sortBy": "relevance"},
        )
        response.raise_for_status()
    except Exception:
        return None
    result = _parse_arxiv_feed(response.text, expected_title=title)
    return result


async def fetch_academic_page(client: httpx.AsyncClient, url: str, source_hit: str) -> EnrichmentResult | None:
    try:
        response = await client.get(url)
        response.raise_for_status()
    except Exception:
        return None
    return parse_academic_page_html(response.text, source_hit=source_hit)


def _parse_arxiv_feed(raw_xml: str, expected_title: str | None = None) -> EnrichmentResult | None:
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return None
    expected_key = title_key(expected_title) if expected_title else None
    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        title = clean_text(title_el.text if title_el is not None else "")
        if expected_key and title_key(title) != expected_key:
            continue
        entry_id_el = entry.find("atom:id", ns)
        arxiv_id = None
        if entry_id_el is not None and entry_id_el.text:
            arxiv_id = parse_url_ids(entry_id_el.text).arxiv_id
        doi_el = entry.find("arxiv:doi", ns)
        summary_el = entry.find("atom:summary", ns)
        authors = []
        for author_el in entry.findall("atom:author", ns):
            name_el = author_el.find("atom:name", ns)
            if name_el is not None and clean_text(name_el.text):
                authors.append(clean_text(name_el.text))
        result = EnrichmentResult(source_hits=["arxiv"])
        result.arxiv_id = arxiv_id
        result.doi = normalize_doi(doi_el.text if doi_el is not None else None)
        result.abstract = clean_text(summary_el.text if summary_el is not None else "") or None
        result.authors = authors
        return result
    return None


async def fetch_openalex(client: httpx.AsyncClient, row: dict[str, Any]) -> EnrichmentResult | None:
    doi = normalize_doi(row.get("doi"))
    work = None
    if doi:
        work = await _fetch_openalex_work_by_doi(client, doi)
    if work is None:
        work = await _fetch_openalex_work_by_title(client, clean_text(row.get("title")), row.get("venue_year"))
    if not work:
        return None

    result = EnrichmentResult(source_hits=["openalex"])
    ids = work.get("ids") if isinstance(work.get("ids"), dict) else {}
    result.doi = normalize_doi(work.get("doi") or ids.get("doi"))
    result.arxiv_id = _arxiv_id_from_openalex(work)
    result.abstract = decode_openalex_abstract(work.get("abstract_inverted_index"))
    result.affiliations = affiliation_mappings_from_openalex(work)
    result.authors = [
        clean_text((a.get("author") or {}).get("display_name") or a.get("raw_author_name"))
        for a in (work.get("authorships") or [])
        if isinstance(a, dict)
    ]
    result.authors = [item for item in result.authors if item]
    return result


async def _fetch_openalex_work_by_doi(client: httpx.AsyncClient, doi: str) -> dict[str, Any] | None:
    try:
        response = await client.get(f"{OPENALEX_WORKS_URL}/https://doi.org/{quote(doi, safe='/')}")
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


async def _fetch_openalex_work_by_title(
    client: httpx.AsyncClient,
    title: str,
    year: Any,
) -> dict[str, Any] | None:
    if not title:
        return None
    params: dict[str, str] = {
        "search": title,
        "per-page": "5",
        "select": "id,doi,title,display_name,publication_year,ids,abstract_inverted_index,authorships",
    }
    year_text = clean_text(year)
    if year_text.isdigit():
        params["filter"] = f"from_publication_date:{year_text}-01-01,to_publication_date:{year_text}-12-31"
    try:
        response = await client.get(f"{OPENALEX_WORKS_URL}?{urlencode(params)}")
        response.raise_for_status()
        results = response.json().get("results") or []
    except Exception:
        return None
    expected = title_key(title)
    best = None
    best_score = 0
    for work in results:
        if not isinstance(work, dict):
            continue
        candidate_title = clean_text(work.get("display_name") or work.get("title"))
        candidate = title_key(candidate_title)
        if not candidate:
            continue
        if candidate == expected:
            return work
        score = _title_overlap(expected, candidate)
        if score > best_score:
            best = work
            best_score = score
    return best if best_score >= 0.86 else None


def _title_overlap(expected: str, candidate: str) -> float:
    expected_tokens = set(expected.split())
    candidate_tokens = set(candidate.split())
    if not expected_tokens or not candidate_tokens:
        return 0.0
    return len(expected_tokens & candidate_tokens) / len(expected_tokens | candidate_tokens)


def _arxiv_id_from_openalex(work: dict[str, Any]) -> str | None:
    ids = work.get("ids") if isinstance(work.get("ids"), dict) else {}
    for value in ids.values():
        parsed = parse_url_ids(clean_text(value))
        if parsed.arxiv_id:
            return parsed.arxiv_id
    primary = work.get("primary_location")
    if isinstance(primary, dict):
        parsed = parse_url_ids(primary.get("landing_page_url"), primary.get("pdf_url"))
        if parsed.arxiv_id:
            return parsed.arxiv_id
    return None


def _pdf_first_page_text(pdf_bytes: bytes) -> str | None:
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if not reader.pages:
            return None
        return reader.pages[0].extract_text() or None
    except Exception:
        return None


def _candidate_pdf_affiliation_lines(first_page_text: str) -> list[str]:
    header_text = first_page_text
    section_match = _PDF_PAPER_SECTION_RE.search(header_text)
    if section_match:
        header_text = header_text[: section_match.start()]
    lines: list[str] = []
    for raw_line in header_text.splitlines():
        line = clean_text(raw_line)
        if not line:
            continue
        if _EMAIL_RE.search(line):
            continue
        if not _AFFILIATION_LINE_RE.search(line):
            continue
        line = _PDF_PREFIX_MARK_RE.sub("", line).strip(" ,;")
        if len(line) < 4:
            continue
        if line not in lines:
            lines.append(line)
    return lines[:8]


def affiliations_from_pdf_first_page(
    first_page_text: str | None,
    authors: list[str],
) -> list[dict[str, Any]]:
    if not first_page_text or not authors:
        return []
    affiliation_lines = _candidate_pdf_affiliation_lines(first_page_text)
    if not affiliation_lines:
        return []
    affiliation = "; ".join(affiliation_lines)
    return [
        {
            "author_order": idx,
            "author_name": author,
            "affiliation": affiliation,
            "evidence": {"source": "pdf_first_page"},
        }
        for idx, author in enumerate(authors, start=1)
        if clean_text(author)
    ]


async def fetch_pdf_first_page_affiliations(
    client: httpx.AsyncClient,
    row: dict[str, Any],
    authors: list[str],
    *,
    limiter: AsyncRateLimiter | None,
    max_pdf_bytes: int,
) -> EnrichmentResult | None:
    if clean_text(row.get("source_id")) not in PDF_AFFILIATION_SOURCE_IDS:
        return None
    pdf_url = clean_text(row.get("pdf_url"))
    if not pdf_url:
        detail_url = clean_text(row.get("detail_url"))
        page_source_hit = academic_page_source_hit(detail_url)
        if detail_url and page_source_hit:
            try:
                response = await client.get(detail_url)
                response.raise_for_status()
                pdf_url = clean_text(pdf_url_from_academic_page(detail_url, response.text))
            except Exception:
                pdf_url = ""
    if not pdf_url:
        return None
    try:
        if limiter is not None:
            await limiter.wait()
        response = await client.get(pdf_url)
        response.raise_for_status()
    except Exception:
        return None
    if max_pdf_bytes > 0 and len(response.content) > max_pdf_bytes:
        return None
    first_page_text = await asyncio.to_thread(_pdf_first_page_text, response.content)
    affiliations = affiliations_from_pdf_first_page(first_page_text, authors)
    if not affiliations:
        return None
    result = EnrichmentResult(source_hits=["pdf_first_page"])
    result.affiliations = affiliations
    return result


def combine_results(results: list[EnrichmentResult | None]) -> EnrichmentResult:
    combined = EnrichmentResult()
    for result in results:
        if result is None:
            continue
        combined.source_hits.extend(result.source_hits)
        if not combined.doi and result.doi:
            combined.doi = result.doi
        if not combined.arxiv_id and result.arxiv_id:
            combined.arxiv_id = result.arxiv_id
        if result.abstract and len(result.abstract) > len(combined.abstract or ""):
            combined.abstract = result.abstract
        if len(result.authors) > len(combined.authors):
            combined.authors = result.authors
        if _affiliation_score(result.affiliations) > _affiliation_score(combined.affiliations):
            combined.affiliations = result.affiliations
        if _profile_list_score(result.author_descriptions) > _profile_list_score(
            combined.author_descriptions
        ):
            combined.author_descriptions = result.author_descriptions
        if _profile_list_score(result.author_experiences) > _profile_list_score(
            combined.author_experiences
        ):
            combined.author_experiences = result.author_experiences
        if _profile_list_score(result.profile_flags) > _profile_list_score(combined.profile_flags):
            combined.profile_flags = result.profile_flags
        if len(result.openreview_authorids) > len(combined.openreview_authorids):
            combined.openreview_authorids = result.openreview_authorids
    combined.source_hits = sorted(set(combined.source_hits))
    return combined


async def enrich_row(
    client: httpx.AsyncClient,
    row: dict[str, Any],
    *,
    max_profile_requests: int,
    enable_arxiv_title_search: bool,
    enable_openalex: bool,
    enable_academic_monitor: bool,
    enable_pdf_first_page: bool,
    openreview_limiter: AsyncRateLimiter | None,
    openreview_profile_cache: dict[str, dict[str, Any] | None] | None,
    pdf_limiter: AsyncRateLimiter | None,
    max_pdf_bytes: int,
) -> tuple[dict[str, Any], EnrichmentResult, dict[str, Any]]:
    ids = parse_url_ids(row.get("detail_url"), row.get("pdf_url"))
    if not ids.arxiv_id:
        ids.arxiv_id = normalize_arxiv_id(row.get("arxiv_id"))
    if not ids.doi:
        ids.doi = normalize_doi(row.get("doi"))

    tasks = []
    if enable_openalex:
        tasks.append(fetch_openalex(client, row))
    if ids.openreview_id:
        tasks.append(
            fetch_openreview(
                client,
                ids.openreview_id,
                max_profile_requests=max_profile_requests,
                limiter=openreview_limiter,
                profile_cache=openreview_profile_cache,
            )
        )
    detail_url = clean_text(row.get("detail_url"))
    page_source_hit = academic_page_source_hit(detail_url)
    if page_source_hit:
        tasks.append(fetch_academic_page(client, detail_url, page_source_hit))
    if ids.arxiv_id:
        tasks.append(fetch_arxiv_by_id(client, ids.arxiv_id))
    elif enable_arxiv_title_search:
        tasks.append(fetch_arxiv_by_title(client, clean_text(row.get("title"))))

    results = await asyncio.gather(*tasks)
    combined = combine_results(results)
    current_affiliation_score = _affiliation_score(row.get("affiliations"))
    if enable_pdf_first_page and _affiliation_score(combined.affiliations) <= current_affiliation_score:
        pdf_authors = combined.authors or [
            clean_text(value) for value in parse_json_list(row.get("authors")) if clean_text(value)
        ]
        pdf_result = await fetch_pdf_first_page_affiliations(
            client,
            row,
            pdf_authors,
            limiter=pdf_limiter,
            max_pdf_bytes=max_pdf_bytes,
        )
        if pdf_result is not None:
            combined = combine_results([combined, pdf_result])
    if ids.doi and not combined.doi:
        combined.doi = ids.doi
    if ids.arxiv_id and not combined.arxiv_id:
        combined.arxiv_id = ids.arxiv_id
    if enable_academic_monitor and ids.openreview_id and combined.authors:
        author_enrichment = await fetch_author_enrichment_from_academic_monitor(
            client,
            paper_id=clean_text(row.get("paper_id")) or None,
            forum_id=ids.openreview_id,
            authors=combined.authors,
            authorids=combined.openreview_authorids,
            existing_affiliations=combined.affiliations,
        )
        if author_enrichment is not None:
            combined = combine_results([combined, author_enrichment])
    merged = merge_enrichment(row, combined.as_update())
    return merged, combined, asdict(ids)


async def select_candidate_rows(
    pool: Any,
    *,
    limit: int,
    offset: int,
    paper_ids: list[str] | None,
    source_id: str | None,
    venue: str | None,
) -> list[dict[str, Any]]:
    filters = [
        """(
            affiliations IS NULL OR affiliations = '[]'::jsonb
            OR NOT EXISTS (
                SELECT 1 FROM jsonb_array_elements(affiliations) a
                WHERE NULLIF(btrim(a->>'affiliation'), '') IS NOT NULL
            )
            OR author_descriptions IS NULL OR author_descriptions = '[]'::jsonb
            OR author_experiences IS NULL OR author_experiences = '[]'::jsonb
            OR profile_flags IS NULL OR profile_flags = '[]'::jsonb
        )""",
        "COALESCE(detail_url, pdf_url, '') <> ''",
    ]
    params: list[Any] = []
    if paper_ids is not None:
        params.append(paper_ids)
        filters = [f"paper_id = ANY(${len(params)}::text[])"]
    if source_id:
        params.append(source_id)
        filters.append(f"source_id = ${len(params)}")
    if venue:
        params.append(venue)
        filters.append(f"venue = ${len(params)}")
    params.append(limit)
    limit_param = len(params)
    params.append(offset)
    offset_param = len(params)
    sql = f"""
        SELECT
            paper_id, paper_uid, canonical_uid, doi, arxiv_id, title, abstract,
            authors, affiliations, author_descriptions, author_experiences, profile_flags,
            detail_url, pdf_url, venue, venue_year, source_id
        FROM papers
        WHERE {' AND '.join(filters)}
        ORDER BY updated_at ASC NULLS FIRST, created_at ASC NULLS FIRST
        LIMIT ${limit_param}
        OFFSET ${offset_param}
    """
    rows = await pool.fetch(sql, *params)
    return [dict(row) for row in rows]


async def update_row(pool: Any, paper_id: str, merged: dict[str, Any]) -> None:
    await pool.execute(
        """
        UPDATE papers
        SET
            doi = $2,
            arxiv_id = $3,
            abstract = $4,
            authors = $5::jsonb,
            affiliations = $6::jsonb,
            author_descriptions = $7::jsonb,
            author_experiences = $8::jsonb,
            profile_flags = $9::jsonb,
            updated_at = now()
        WHERE paper_id = $1
        """,
        paper_id,
        merged["doi"],
        merged["arxiv_id"],
        merged["abstract"],
        json.dumps(merged["authors"], ensure_ascii=False),
        json.dumps(merged["affiliations"], ensure_ascii=False),
        json.dumps(merged["author_descriptions"], ensure_ascii=False),
        json.dumps(merged["author_experiences"], ensure_ascii=False),
        json.dumps(merged["profile_flags"], ensure_ascii=False),
    )


async def run(args: argparse.Namespace) -> None:
    await init_pool(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=settings.POSTGRES_DB,
    )
    pool = get_pool()
    rows = await select_candidate_rows(
        pool,
        limit=args.limit,
        offset=args.offset,
        paper_ids=read_paper_id_file(Path(args.paper_id_file)) if args.paper_id_file else None,
        source_id=args.source_id,
        venue=args.venue,
    )
    timeout = httpx.Timeout(args.timeout)
    headers = {
        "User-Agent": "DeanAgent paper metadata backfill (mailto:metadata@example.invalid)",
    }
    stats = {
        "candidates": len(rows),
        "updated": 0,
        "with_affiliations": 0,
        "with_abstract": 0,
        "with_doi": 0,
        "with_arxiv_id": 0,
        "with_author_descriptions": 0,
        "with_author_experiences": 0,
        "with_profile_flags": 0,
        "source_hits": {},
        "errors": 0,
    }
    sem = asyncio.Semaphore(args.concurrency)
    openreview_limiter = AsyncRateLimiter(args.openreview_qps)
    pdf_limiter = AsyncRateLimiter(args.pdf_qps)
    openreview_profile_cache: dict[str, dict[str, Any] | None] = {}

    async def process_one(
        index: int,
        row: dict[str, Any],
        client: httpx.AsyncClient,
    ) -> tuple[int, dict[str, Any], dict[str, Any] | None, EnrichmentResult | None, dict[str, Any] | None, str | None]:
        async with sem:
            try:
                merged, combined, ids = await enrich_row(
                    client,
                    row,
                    max_profile_requests=args.max_profile_requests,
                    enable_arxiv_title_search=args.arxiv_title_search,
                    enable_openalex=not args.disable_openalex,
                    enable_academic_monitor=not args.disable_academic_monitor,
                    enable_pdf_first_page=not args.disable_pdf_first_page,
                    openreview_limiter=openreview_limiter,
                    openreview_profile_cache=openreview_profile_cache,
                    pdf_limiter=pdf_limiter,
                    max_pdf_bytes=args.max_pdf_bytes,
                )
            except Exception as exc:  # noqa: BLE001
                return index, row, None, None, None, str(exc)

            changed = (
                normalize_doi(merged["doi"]) != normalize_doi(row.get("doi"))
                or normalize_arxiv_id(merged["arxiv_id"]) != normalize_arxiv_id(row.get("arxiv_id"))
                or clean_text(merged["abstract"]) != clean_text(row.get("abstract"))
                or len(merged["authors"]) != len(parse_json_list(row.get("authors")))
                or _affiliation_score(merged["affiliations"]) > _affiliation_score(row.get("affiliations"))
                or _profile_list_score(merged["author_descriptions"])
                > _profile_list_score(row.get("author_descriptions"))
                or _profile_list_score(merged["author_experiences"])
                > _profile_list_score(row.get("author_experiences"))
                or _profile_list_score(merged["profile_flags"])
                > _profile_list_score(row.get("profile_flags"))
            )
            if changed and not args.dry_run:
                await update_row(pool, row["paper_id"], merged)
            return index, row, merged, combined, ids, None

    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        tasks = [
            asyncio.create_task(process_one(index, row, client))
            for index, row in enumerate(rows, start=1)
        ]
        completed = 0
        for task in asyncio.as_completed(tasks):
            index, row, merged, combined, ids, error = await task
            completed += 1
            if error:
                stats["errors"] += 1
                print(f"[{completed}/{len(rows)}] error {row['paper_id']}: {error}")
                continue
            assert merged is not None
            assert combined is not None
            assert ids is not None
            if _affiliation_score(merged["affiliations"]) > _affiliation_score(row.get("affiliations")):
                stats["with_affiliations"] += 1
            if merged["abstract"] and not clean_text(row.get("abstract")):
                stats["with_abstract"] += 1
            if merged["doi"] and not normalize_doi(row.get("doi")):
                stats["with_doi"] += 1
            if merged["arxiv_id"] and not normalize_arxiv_id(row.get("arxiv_id")):
                stats["with_arxiv_id"] += 1
            if _profile_list_score(merged["author_descriptions"]) > _profile_list_score(
                row.get("author_descriptions")
            ):
                stats["with_author_descriptions"] += 1
            if _profile_list_score(merged["author_experiences"]) > _profile_list_score(
                row.get("author_experiences")
            ):
                stats["with_author_experiences"] += 1
            if _profile_list_score(merged["profile_flags"]) > _profile_list_score(
                row.get("profile_flags")
            ):
                stats["with_profile_flags"] += 1
            for source in combined.source_hits:
                stats["source_hits"][source] = stats["source_hits"].get(source, 0) + 1

            changed = (
                normalize_doi(merged["doi"]) != normalize_doi(row.get("doi"))
                or normalize_arxiv_id(merged["arxiv_id"]) != normalize_arxiv_id(row.get("arxiv_id"))
                or clean_text(merged["abstract"]) != clean_text(row.get("abstract"))
                or len(merged["authors"]) != len(parse_json_list(row.get("authors")))
                or _affiliation_score(merged["affiliations"]) > _affiliation_score(row.get("affiliations"))
                or _profile_list_score(merged["author_descriptions"])
                > _profile_list_score(row.get("author_descriptions"))
                or _profile_list_score(merged["author_experiences"])
                > _profile_list_score(row.get("author_experiences"))
                or _profile_list_score(merged["profile_flags"])
                > _profile_list_score(row.get("profile_flags"))
            )
            if changed:
                stats["updated"] += 1

            if args.verbose or completed % args.progress_every == 0 or completed == len(rows):
                print(
                    f"[{completed}/{len(rows)}] paper_id={row['paper_id']} "
                    f"row_index={index} "
                    f"hits={','.join(combined.source_hits) or '-'} "
                    f"ids={ids} changed={changed}"
                )

    print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))
    await close_pool()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enrich papers missing affiliations via URL-driven OpenAlex/OpenReview/arXiv lookups."
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--source-id")
    parser.add_argument("--venue")
    parser.add_argument("--paper-id-file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument(
        "--max-profile-requests",
        type=int,
        default=0,
        help="Max OpenReview author profiles per paper; 0 means all authors.",
    )
    parser.add_argument("--openreview-qps", type=float, default=0.8)
    parser.add_argument("--disable-openalex", action="store_true")
    parser.add_argument("--disable-academic-monitor", action="store_true")
    parser.add_argument("--disable-pdf-first-page", action="store_true")
    parser.add_argument(
        "--pdf-qps",
        type=float,
        default=0.3,
        help="Max PDF first-page fetches per second; keep conservative to avoid venue-side rate limits.",
    )
    parser.add_argument(
        "--max-pdf-bytes",
        type=int,
        default=12_000_000,
        help="Skip PDF first-page fallback when the downloaded PDF exceeds this size; 0 disables the size check.",
    )
    parser.add_argument("--arxiv-title-search", action="store_true")
    parser.add_argument("--progress-every", type=int, default=10)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
