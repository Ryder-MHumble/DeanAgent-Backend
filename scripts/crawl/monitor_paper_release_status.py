from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_YEARS = (2025, 2026)
PAPER_SOURCE_FILE = "paper/top_conference_papers.yaml"


@dataclass(slots=True)
class OfficialCheck:
    applicable: bool
    published: bool
    official_count: int | None
    evidence_url: str
    reason: str


@dataclass(slots=True)
class MonitorRow:
    source_id: str
    venue: str
    year: int
    db_count: int
    official_count: int | None
    official_status: str
    verdict: str
    reason: str
    official_evidence_url: str


def classify_verdict(db_count: int, check: OfficialCheck) -> tuple[str, str]:
    if not check.applicable:
        return "not_applicable_year", check.reason
    if not check.published:
        return "not_published_yet", check.reason
    if check.official_count is not None:
        if db_count == check.official_count:
            return (
                "published_and_in_db",
                f"{check.reason} DB count matches official count ({db_count}).",
            )
        return (
            "published_but_missing_in_db",
            f"{check.reason} Official count is {check.official_count}, but DB count is {db_count}.",
        )
    if db_count > 0:
        return "published_and_in_db", f"{check.reason} DB count is {db_count}."
    return (
        "published_but_missing_in_db",
        f"{check.reason} Official source is published, but DB count is 0.",
    )


def _official_status(check: OfficialCheck) -> str:
    if not check.applicable:
        return "not_applicable_year"
    if not check.published:
        return "not_published_yet"
    return "published"


def _year_config(config: dict[str, Any], year: int) -> dict[str, Any]:
    raw = config.get("year_configs")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and int(item.get("year") or 0) == year:
                return {**config, **item}
    return {**config, "year": year}


def _paper_configs() -> list[dict[str, Any]]:
    from app.scheduler.manager import load_all_source_configs

    configs = []
    for config in load_all_source_configs():
        if config.get("dimension") != "paper":
            continue
        if config.get("entity_family") != "paper_record":
            continue
        if config.get("source_file_path") != PAPER_SOURCE_FILE:
            continue
        configs.append(config)
    return configs


async def _db_counts(source_ids: list[str], years: list[int]) -> dict[tuple[str, int], int]:
    from app.config import settings
    from app.db.pool import close_pool, fetch, init_pool

    await init_pool(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=settings.POSTGRES_DB,
    )
    try:
        rows = await fetch(
            """
            SELECT source_id, venue_year, COUNT(*) AS c
            FROM papers
            WHERE source_id = ANY($1::text[])
              AND venue_year = ANY($2::int[])
            GROUP BY source_id, venue_year
            """,
            source_ids,
            years,
        )
    finally:
        await close_pool()

    counts: dict[tuple[str, int], int] = {}
    for row in rows:
        counts[(str(row["source_id"]), int(row["venue_year"]))] = int(row["c"])
    return counts


async def _get_text(
    client: httpx.AsyncClient,
    url: str,
    *,
    retries: int = 3,
) -> tuple[int, str]:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            response = await client.get(url)
            return response.status_code, response.text
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt + 1 < retries:
                await asyncio.sleep(1 + attempt)
    raise last_exc if last_exc is not None else RuntimeError(f"GET failed: {url}")


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    retries: int = 3,
) -> tuple[int, dict[str, Any] | list[Any] | None]:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            response = await client.get(url)
            if response.status_code >= 400:
                return response.status_code, None
            return response.status_code, response.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_exc = exc
            if attempt + 1 < retries:
                await asyncio.sleep(1 + attempt)
    raise last_exc if last_exc is not None else RuntimeError(f"GET failed: {url}")


async def _check_acl_like(
    client: httpx.AsyncClient,
    config: dict[str, Any],
    year: int,
) -> OfficialCheck:
    from app.crawlers.parsers.aclanthology import ACLAnthologyCrawler

    year_cfg = _year_config(config, year)
    track = str(year_cfg["track"])
    bib_url = f"https://aclanthology.org/volumes/{year}.{track}.bib"
    status_code, text = await _get_text(client, bib_url)
    if status_code == 404:
        venue_slug = str(config["venue"]).lower()
        venue_url = f"https://aclanthology.org/venues/{venue_slug}/"
        return OfficialCheck(
            applicable=True,
            published=False,
            official_count=None,
            evidence_url=venue_url,
            reason=f"{config['venue']} {year} volume `{year}.{track}.bib` is not available on ACL Anthology yet.",
        )
    entries = ACLAnthologyCrawler._parse_bib(text)
    return OfficialCheck(
        applicable=True,
        published=True,
        official_count=len(entries),
        evidence_url=bib_url,
        reason=f"ACL Anthology volume `{year}.{track}.bib` currently contains {len(entries)} paper entries.",
    )


async def _check_ijcai(client: httpx.AsyncClient, config: dict[str, Any], year: int) -> OfficialCheck:
    from app.crawlers.parsers.ijcai_proceedings import IJCAIProceedingsCrawler

    year_cfg = _year_config(config, year)
    proceedings_url = f"https://www.ijcai.org/proceedings/{year}/"
    status_code, text = await _get_text(client, proceedings_url)
    if status_code == 404:
        dates_url = f"https://{year}.ijcai.org/important-dates/"
        dates_status, dates_html = await _get_text(client, dates_url)
        dates_reason = ""
        if dates_status == 200:
            dates_text = BeautifulSoup(dates_html, "lxml").get_text(" ", strip=True)
            if "Camera Ready Copy" in dates_text:
                dates_reason = " The important dates page still shows the camera-ready timeline."
        return OfficialCheck(
            applicable=True,
            published=False,
            official_count=None,
            evidence_url=proceedings_url,
            reason=f"IJCAI proceedings page `{proceedings_url}` returns 404.{dates_reason}".strip(),
        )
    rows = IJCAIProceedingsCrawler._parse_page(
        text,
        year_cfg.get("track_filter") or [],
        year,
    )
    return OfficialCheck(
        applicable=True,
        published=True,
        official_count=len(rows),
        evidence_url=proceedings_url,
        reason=f"IJCAI proceedings page currently contains {len(rows)} filtered papers.",
    )


async def _check_neurips(client: httpx.AsyncClient, config: dict[str, Any], year: int) -> OfficialCheck:
    from app.crawlers.parsers.nips_papers_cc import _PAPER_ROW_RE, _TRACK_LABEL

    list_url = f"https://papers.nips.cc/paper_files/paper/{year}"
    status_code, text = await _get_text(client, list_url)
    include_tracks = config.get("include_tracks") or list(_TRACK_LABEL.keys())
    if status_code == 200:
        matches = [
            match
            for match in _PAPER_ROW_RE.findall(text)
            if match[0] in include_tracks
        ]
        return OfficialCheck(
            applicable=True,
            published=True,
            official_count=len(matches),
            evidence_url=list_url,
            reason=f"NeurIPS proceedings page currently contains {len(matches)} configured paper rows.",
        )

    posters_url = f"https://neurips.cc/static/virtual/data/neurips-{year}-orals-posters.json"
    abstracts_url = f"https://neurips.cc/static/virtual/data/neurips-{year}-abstracts.json"
    posters_status, posters_payload = await _get_json(client, posters_url)
    abstracts_status, _ = await _get_json(client, abstracts_url)
    posters_count = None
    if isinstance(posters_payload, dict):
        posters_count = int(posters_payload.get("count") or 0)

    if posters_status == 200 and posters_count and posters_count > 0 and abstracts_status == 200:
        return OfficialCheck(
            applicable=True,
            published=True,
            official_count=None,
            evidence_url=posters_url,
            reason=(
                "NeurIPS proceedings page is not live yet, but the virtual data feed already contains "
                f"{posters_count} poster/oral entries."
            ),
        )

    return OfficialCheck(
        applicable=True,
        published=False,
        official_count=None,
        evidence_url=posters_url,
        reason=(
            f"NeurIPS proceedings page `{list_url}` is not available; virtual JSON count is "
            f"{posters_count or 0} and abstracts JSON status is {abstracts_status}."
        ),
    )


async def _check_cvf(client: httpx.AsyncClient, config: dict[str, Any], year: int) -> OfficialCheck:
    from app.crawlers.parsers.cvf_openaccess import CVFCrawler

    year_cfg = _year_config(config, year)
    if year_cfg.get("source_format") == "cvf_virtual_page":
        list_url = str(year_cfg["url"])
        status_code, text = await _get_text(client, list_url)
        if status_code == 404:
            return OfficialCheck(
                applicable=True,
                published=False,
                official_count=None,
                evidence_url=list_url,
                reason=f"{config['venue']} {year} virtual papers page is not available yet.",
            )
        rows = CVFCrawler._parse_virtual_rows(text, list_url=list_url, year=year)
        return OfficialCheck(
            applicable=True,
            published=bool(rows),
            official_count=len(rows) if rows else None,
            evidence_url=list_url,
            reason=f"{config['venue']} virtual papers page currently exposes {len(rows)} paper links.",
        )

    list_url = str(year_cfg.get("url") or f"https://openaccess.thecvf.com/{config['venue']}{year}?day=all")
    status_code, text = await _get_text(client, list_url)
    if status_code == 404:
        return OfficialCheck(
            applicable=True,
            published=False,
            official_count=None,
            evidence_url=list_url,
            reason=f"{config['venue']} OpenAccess page `{list_url}` is not available yet.",
        )
    rows = CVFCrawler._parse_rows(text)
    return OfficialCheck(
        applicable=True,
        published=True,
        official_count=len(rows),
        evidence_url=list_url,
        reason=f"{config['venue']} OpenAccess page currently contains {len(rows)} paper rows.",
    )


async def _check_iccv(client: httpx.AsyncClient, config: dict[str, Any], year: int) -> OfficialCheck:
    if year % 2 == 0:
        evidence_url = f"https://openaccess.thecvf.com/ICCV{year}"
        return OfficialCheck(
            applicable=False,
            published=False,
            official_count=None,
            evidence_url=evidence_url,
            reason=f"ICCV runs on odd years; {year} is not an ICCV year.",
        )
    return await _check_cvf(client, config, year)


async def _check_eccv(client: httpx.AsyncClient, config: dict[str, Any], year: int) -> OfficialCheck:
    from app.crawlers.parsers.ecva_papers import ECVACrawler

    if year % 2 == 1:
        return OfficialCheck(
            applicable=False,
            published=False,
            official_count=None,
            evidence_url=f"https://eccv.ecva.net/Conferences/{year}",
            reason=f"ECCV runs on even years; {year} is not an ECCV year.",
        )

    if year <= 2024:
        list_url = str(config.get("url") or "https://www.ecva.net/papers.php")
        status_code, text = await _get_text(client, list_url)
        if status_code == 404:
            return OfficialCheck(
                applicable=True,
                published=False,
                official_count=None,
                evidence_url=list_url,
                reason=f"ECCV papers index `{list_url}` is not available.",
            )
        block = ECVACrawler._extract_year_block(text, year)
        rows = ECVACrawler._parse_year_block(block, year) if block else []
        return OfficialCheck(
            applicable=True,
            published=True,
            official_count=len(rows),
            evidence_url=list_url,
            reason=f"ECVA papers index currently contains {len(rows)} ECCV {year} rows.",
        )

    papers_url = f"https://eccv.ecva.net/virtual/{year}/papers.html"
    json_url = f"https://eccv.ecva.net/static/virtual/data/eccv-{year}-orals-posters.json"
    json_status, payload = await _get_json(client, json_url)
    count = 0
    if isinstance(payload, dict):
        count = int(payload.get("count") or 0)
    if json_status == 200 and count > 0:
        return OfficialCheck(
            applicable=True,
            published=True,
            official_count=None,
            evidence_url=json_url,
            reason=f"ECCV virtual JSON currently reports {count} poster/oral entries.",
        )
    return OfficialCheck(
        applicable=True,
        published=False,
        official_count=None,
        evidence_url=papers_url,
        reason=f"ECCV virtual papers feed for {year} is not populated yet; JSON count is {count}.",
    )


async def _openreview_note_count(client: httpx.AsyncClient, venue_id: str) -> int:
    count = 0
    offset = 0
    limit = 1000
    while True:
        params = {
            "content.venueid": venue_id,
            "limit": str(limit),
            "offset": str(offset),
        }
        url = f"https://api2.openreview.net/notes?{urlencode(params)}"
        status_code, payload = await _get_json(client, url)
        if status_code >= 400 or not isinstance(payload, dict):
            break
        notes = payload.get("notes") or []
        if not isinstance(notes, list) or not notes:
            break
        count += len(notes)
        if len(notes) < limit:
            break
        offset += limit
    return count


async def _openreview_journal_year_count(client: httpx.AsyncClient, venue_id: str, year: int) -> int:
    count = 0
    offset = 0
    limit = 1000
    while True:
        params = {
            "content.venueid": venue_id,
            "limit": str(limit),
            "offset": str(offset),
            "sort": "pdate:desc",
        }
        url = f"https://api2.openreview.net/notes?{urlencode(params)}"
        status_code, payload = await _get_json(client, url)
        if status_code >= 400 or not isinstance(payload, dict):
            break
        notes = payload.get("notes") or []
        if not isinstance(notes, list) or not notes:
            break
        stop = False
        for note in notes:
            if not isinstance(note, dict):
                continue
            timestamp = note.get("pdate") or note.get("odate") or note.get("cdate")
            if not isinstance(timestamp, int):
                continue
            note_year = datetime.fromtimestamp(timestamp / 1000, timezone.utc).year
            if note_year == year:
                count += 1
            elif note_year < year:
                stop = True
        if stop or len(notes) < limit:
            break
        offset += limit
    return count


async def _check_openreview_venue(
    client: httpx.AsyncClient,
    config: dict[str, Any],
    year: int,
) -> OfficialCheck:
    year_cfg = _year_config(config, year)
    if year_cfg.get("source_format") == "icml_virtual":
        data_url = str(year_cfg["data_url"])
        status_code, payload = await _get_json(client, data_url)
        if status_code == 404:
            return OfficialCheck(
                applicable=True,
                published=False,
                official_count=None,
                evidence_url=data_url,
                reason=f"{config['venue']} virtual JSON `{data_url}` is not available yet.",
            )
        records = payload.get("results", []) if isinstance(payload, dict) else payload
        count = len(records) if isinstance(records, list) else 0
        return OfficialCheck(
            applicable=True,
            published=count > 0,
            official_count=count if count > 0 else None,
            evidence_url=data_url,
            reason=f"{config['venue']} virtual JSON currently contains {count} records.",
        )

    venue_id = str(year_cfg.get("venue_id") or "")
    count = await _openreview_note_count(client, venue_id)
    return OfficialCheck(
        applicable=True,
        published=count > 0,
        official_count=count if count > 0 else None,
        evidence_url=f"https://api2.openreview.net/notes?content.venueid={quote(venue_id)}",
        reason=f"OpenReview venue `{venue_id}` currently returns {count} notes.",
    )


async def _check_icml(client: httpx.AsyncClient, config: dict[str, Any], year: int) -> OfficialCheck:
    from app.crawlers.parsers.openreview_api import OpenReviewCrawler

    year_cfg = _year_config(config, year)
    venue_id = str(year_cfg.get("venue_id") or "")
    if venue_id:
        count = await _openreview_note_count(client, venue_id)
        if count > 0:
            return OfficialCheck(
                applicable=True,
                published=True,
                official_count=count,
                evidence_url=f"https://api2.openreview.net/notes?content.venueid={quote(venue_id)}",
                reason=f"OpenReview venue `{venue_id}` currently returns {count} notes.",
            )

    json_url = f"https://icml.cc/static/virtual/data/icml-{year}-orals-posters.json"
    status_code, payload = await _get_json(client, json_url)
    if status_code == 200:
        records = payload.get("results", []) if isinstance(payload, dict) else payload
        filtered_records = OpenReviewCrawler._filter_icml_virtual_records(records or [])
        count = len(filtered_records)
        return OfficialCheck(
            applicable=True,
            published=count > 0,
            official_count=count if count > 0 else None,
            evidence_url=json_url,
            reason=(
                "ICML virtual JSON currently contains "
                f"{count} filtered paper/forum records after deduplicating oral/poster rows "
                "and excluding `Position:` special-track entries."
            ),
        )
    return OfficialCheck(
        applicable=True,
        published=False,
        official_count=None,
        evidence_url=json_url,
        reason=(
            f"ICML OpenReview venue `{venue_id}` currently returns 0 notes and "
            f"virtual JSON `{json_url}` is not available yet."
        ),
    )


async def _check_tmlr(client: httpx.AsyncClient, config: dict[str, Any], year: int) -> OfficialCheck:
    venue_id = str(config.get("venue_id") or "TMLR")
    count = await _openreview_journal_year_count(client, venue_id, year)
    return OfficialCheck(
        applicable=True,
        published=count > 0,
        official_count=count if count > 0 else None,
        evidence_url=f"https://api2.openreview.net/notes?content.venueid={quote(venue_id)}",
        reason=f"TMLR OpenReview journal feed currently contains {count} records for {year}.",
    )


async def _check_jmlr(client: httpx.AsyncClient, config: dict[str, Any], year: int) -> OfficialCheck:
    from app.crawlers.parsers.jmlr_papers import JMLRPapersCrawler

    year_cfg = _year_config(config, year)
    volume = int(year_cfg.get("volume") or year - 1999)
    list_url = str(year_cfg.get("url") or f"https://www.jmlr.org/papers/v{volume}/")
    status_code, text = await _get_text(client, list_url)
    if status_code == 404:
        return OfficialCheck(
            applicable=True,
            published=False,
            official_count=None,
            evidence_url=list_url,
            reason=f"JMLR volume page `{list_url}` is not available yet.",
        )
    rows = JMLRPapersCrawler._parse_rows(text, volume=volume)
    return OfficialCheck(
        applicable=True,
        published=bool(rows),
        official_count=len(rows) if rows else None,
        evidence_url=list_url,
        reason=f"JMLR volume page currently contains {len(rows)} paper rows.",
    )


async def _check_jair(client: httpx.AsyncClient, config: dict[str, Any], year: int) -> OfficialCheck:
    from app.crawlers.parsers.jair_oai import JAIROAICrawler

    base_url = str(config.get("oai_url") or "https://www.jair.org/index.php/jair/oai")
    token: str | None = None
    count = 0
    pages = 0
    while True:
        pages += 1
        if token:
            url = f"{base_url}?verb=ListRecords&resumptionToken={quote(token)}"
        else:
            params = {
                "verb": "ListRecords",
                "metadataPrefix": "oai_dc",
                "from": f"{year}-01-01",
            }
            url = f"{base_url}?{urlencode(params)}"
        status_code, text = await _get_text(client, url)
        if status_code >= 400:
            break
        records, token = JAIROAICrawler._parse_page(text, {year})
        count += len(records)
        if not token or pages >= 20:
            break
    return OfficialCheck(
        applicable=True,
        published=count > 0,
        official_count=count if count > 0 else None,
        evidence_url=base_url,
        reason=f"JAIR OAI feed currently returns {count} records for {year}.",
    )


async def _check_aaai(client: httpx.AsyncClient, config: dict[str, Any], year: int) -> OfficialCheck:
    from app.crawlers.parsers.ojs_aaai import _ARTICLE_RE

    year_cfg = _year_config(config, year)
    issue_ids = year_cfg.get("issue_ids") or []
    if not isinstance(issue_ids, list) or not issue_ids:
        return OfficialCheck(
            applicable=True,
            published=False,
            official_count=None,
            evidence_url="https://ojs.aaai.org/index.php/AAAI/issue/archive",
            reason=f"AAAI {year} has no configured issue IDs to verify.",
        )

    total = 0
    available_issue_count = 0
    first_issue_url = f"https://ojs.aaai.org/index.php/AAAI/issue/view/{issue_ids[0]}"

    async def fetch_issue(raw_issue_id: Any) -> tuple[int, int, int]:
        issue_id = int(raw_issue_id)
        issue_url = f"https://ojs.aaai.org/index.php/AAAI/issue/view/{issue_id}"
        try:
            status_code, text = await _get_text(client, issue_url)
        except Exception:
            return 0, 0, 1
        if status_code >= 400:
            return 0, 0, 0
        return 1, len(list(_ARTICLE_RE.finditer(text))), 0

    results = await asyncio.gather(*(fetch_issue(raw_issue_id) for raw_issue_id in issue_ids))
    failed_issue_count = 0
    for issue_live, issue_count, issue_failed in results:
        available_issue_count += issue_live
        total += issue_count
        failed_issue_count += issue_failed

    official_count = total if total > 0 and failed_issue_count == 0 else None
    if failed_issue_count > 0:
        reason = (
            f"AAAI configured {len(issue_ids)} issues for {year}; {available_issue_count} issue pages are live, "
            f"{failed_issue_count} issue pages failed during the probe, and the partial probe saw {total} article rows."
        )
    else:
        reason = (
            f"AAAI configured {len(issue_ids)} issues for {year}; {available_issue_count} issue pages are live "
            f"and currently expose {total} article rows."
        )

    return OfficialCheck(
        applicable=True,
        published=total > 0,
        official_count=official_count,
        evidence_url=first_issue_url,
        reason=reason,
    )


async def _run_official_check(
    client: httpx.AsyncClient,
    config: dict[str, Any],
    year: int,
) -> OfficialCheck:
    source_id = str(config["id"])
    if source_id in {"acl_long", "acl_short", "emnlp_main"}:
        return await _check_acl_like(client, config, year)
    if source_id == "ijcai":
        return await _check_ijcai(client, config, year)
    if source_id == "neurips":
        return await _check_neurips(client, config, year)
    if source_id == "cvpr":
        return await _check_cvf(client, config, year)
    if source_id == "iccv":
        return await _check_iccv(client, config, year)
    if source_id == "eccv":
        return await _check_eccv(client, config, year)
    if source_id == "iclr":
        return await _check_openreview_venue(client, config, year)
    if source_id == "icml":
        return await _check_icml(client, config, year)
    if source_id == "tmlr":
        return await _check_tmlr(client, config, year)
    if source_id == "jmlr":
        return await _check_jmlr(client, config, year)
    if source_id == "jair":
        return await _check_jair(client, config, year)
    if source_id == "aaai":
        return await _check_aaai(client, config, year)
    return OfficialCheck(
        applicable=False,
        published=False,
        official_count=None,
        evidence_url="",
        reason=f"Source `{source_id}` is not supported by this monitor yet.",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor official release status vs DB coverage for top paper sources.",
    )
    parser.add_argument("--source", action="append", help="Specific paper source ID to monitor")
    parser.add_argument("--year", action="append", type=int, help="Specific year to monitor")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of plain text lines")
    return parser.parse_args()


async def _build_rows(args: argparse.Namespace) -> list[MonitorRow]:
    years = sorted(set(args.year or DEFAULT_YEARS))
    configs = _paper_configs()
    if args.source:
        wanted = set(args.source)
        configs = [config for config in configs if config["id"] in wanted]
    source_ids = [str(config["id"]) for config in configs]
    counts = await _db_counts(source_ids, years)

    rows: list[MonitorRow] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (paper release monitor)",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    }
    async with httpx.AsyncClient(
        headers=headers,
        timeout=60.0,
        follow_redirects=True,
    ) as client:
        semaphore = asyncio.Semaphore(4)

        async def build_row(config: dict[str, Any], year: int) -> MonitorRow:
            try:
                async with semaphore:
                    check = await _run_official_check(client, config, year)
            except Exception as exc:  # noqa: BLE001
                detail = str(exc).strip() or type(exc).__name__
                return MonitorRow(
                    source_id=str(config["id"]),
                    venue=str(config.get("venue") or config["id"]),
                    year=year,
                    db_count=counts.get((str(config["id"]), year), 0),
                    official_count=None,
                    official_status="probe_failed",
                    verdict="probe_failed",
                    reason=f"Official probe failed: {detail}",
                    official_evidence_url="",
                )
            db_count = counts.get((str(config["id"]), year), 0)
            verdict, reason = classify_verdict(db_count=db_count, check=check)
            return MonitorRow(
                source_id=str(config["id"]),
                venue=str(config.get("venue") or config["id"]),
                year=year,
                db_count=db_count,
                official_count=check.official_count,
                official_status=_official_status(check),
                verdict=verdict,
                reason=reason,
                official_evidence_url=check.evidence_url,
            )

        tasks = [build_row(config, year) for config in configs for year in years]
        rows = await asyncio.gather(*tasks)
    return list(rows)


def _print_rows(rows: list[MonitorRow], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2))
        return
    for row in rows:
        print(
            " | ".join(
                [
                    f"source_id={row.source_id}",
                    f"venue={row.venue}",
                    f"year={row.year}",
                    f"db_count={row.db_count}",
                    f"official_count={row.official_count if row.official_count is not None else 'unknown'}",
                    f"official_status={row.official_status}",
                    f"verdict={row.verdict}",
                    f"evidence={row.official_evidence_url}",
                    f"reason={row.reason}",
                ]
            )
        )


async def main() -> None:
    args = _parse_args()
    rows = await _build_rows(args)
    _print_rows(rows, as_json=bool(args.json))


if __name__ == "__main__":
    asyncio.run(main())
