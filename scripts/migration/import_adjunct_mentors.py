#!/usr/bin/env python3
"""Import mentor/community data from CSV files into scholars table.

Usage:
  ./.venv/bin/python scripts/migration/import_adjunct_mentors.py --dry-run
  ./.venv/bin/python scripts/migration/import_adjunct_mentors.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

try:
    from scripts.migration.components.runtime import (
        close_postgres_pool,
        get_postgres_pool,
        init_postgres_pool_from_settings,
    )
except ModuleNotFoundError:  # direct execution fallback
    from components.runtime import (  # type: ignore[no-redef]
        close_postgres_pool,
        get_postgres_pool,
        init_postgres_pool_from_settings,
    )

BASIC_CSV = Path("data/scholars/学院导师信息.csv")
AAAI_CSV = Path("data/scholars/AAAI+学院导师.csv")

EDU_CATEGORY = "教育培养"
MENTOR_SUBCATEGORY = "学院学生高校导师"
ADJUNCT_SUBCATEGORY = "兼职导师"

AAAI_COMMUNITY_NAME = "AAAI"
AAAI_COMMUNITY_TYPE = "顶会"
AAAI_COMMUNITY_TAGS = ["AAAI", "顶会", "community:AAAI", "top_conf:AAAI"]

MENTOR_TAGS = ["学院导师", "共建导师"]


def n(text: Any) -> str:
    """Normalize text for matching."""
    if text is None:
        return ""
    return "".join(str(text).replace("\u3000", " ").strip().split()).lower()


def clean_text(text: Any) -> str:
    return str(text or "").strip()


def clean_email(text: Any) -> str:
    return "".join(str(text or "").strip().split())


def parse_json_maybe(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    if not isinstance(raw, str):
        return default
    text = raw.strip()
    if not text:
        return default
    value: Any = text
    # Some legacy rows store JSON as nested-encoded strings (e.g. "\"{...}\"").
    for _ in range(3):
        if not isinstance(value, str):
            return value
        token = value.strip()
        if not token:
            return default
        try:
            parsed = json.loads(token)
        except Exception:
            return default
        value = parsed
    return value if value is not None else default


def decode_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 0, f"Failed to decode {path}")


def load_csv(path: Path) -> list[dict[str, str]]:
    text = decode_text(path)
    reader = csv.DictReader(io.StringIO(text, newline=""))
    rows: list[dict[str, str]] = []
    for row in reader:
        rows.append({str(k or "").strip(): clean_text(v) for k, v in row.items()})
    return rows


def normalize_adjunct(raw: Any) -> dict[str, str]:
    data = parse_json_maybe(raw, {})
    if not isinstance(data, dict):
        data = {}
    result = {
        "status": clean_text(data.get("status", "")),
        "type": clean_text(data.get("type", "")),
        "agreement_type": clean_text(data.get("agreement_type", "")),
        "agreement_period": clean_text(data.get("agreement_period", "")),
        "recommender": clean_text(data.get("recommender", "")),
    }
    if not result["status"]:
        result["status"] = "已签署"
    if not result["recommender"]:
        result["recommender"] = "培养部"
    return result


def empty_adjunct() -> dict[str, str]:
    return {
        "status": "",
        "type": "",
        "agreement_type": "",
        "agreement_period": "",
        "recommender": "",
    }


def to_list_text(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [clean_text(x) for x in raw if clean_text(x)]
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        parsed = parse_json_maybe(text, None)
        if isinstance(parsed, list):
            return [clean_text(x) for x in parsed if clean_text(x)]
        # fallback split for non-json style strings
        out: list[str] = []
        tmp = text
        for sep in ["；", ";", "，", ",", "、", "|", "/"]:
            tmp = tmp.replace(sep, "|")
        for token in tmp.split("|"):
            val = clean_text(token)
            if val:
                out.append(val)
        return out
    return []


def merge_unique_text_list(existing: list[str], incoming: list[str], limit: int = 30) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in list(existing or []) + list(incoming or []):
        v = clean_text(item)
        if not v:
            continue
        key = n(v)
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
        if len(out) >= limit:
            break
    return out


def pick_best(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        rows,
        key=lambda r: (
            1 if clean_text(normalize_adjunct(r.get("adjunct_supervisor")).get("status")) else 0,
            1 if clean_text(r.get("updated_at")) else 0,
            len(clean_text(r.get("university"))),
            len(clean_text(r.get("position"))),
        ),
    )


def mentor_hash_id(name: str, university: str) -> str:
    return hashlib.sha256(f"mentor:{name}:{university}".encode("utf-8")).hexdigest()


def aaai_hash_id(name: str, name_en: str, org_main: str, org_all: str) -> str:
    anchor = name or name_en or "unknown"
    org = org_main or org_all or ""
    return hashlib.sha256(f"aaai:{anchor}:{org}".encode("utf-8")).hexdigest()


def merge_tags(existing: Any, incoming: list[str]) -> list[str]:
    base = to_list_text(existing)
    return merge_unique_text_list(base, incoming, limit=60)


def remove_tags(existing: Any, to_remove: list[str]) -> list[str]:
    base = to_list_text(existing)
    remove_set = {n(x) for x in to_remove}
    return [x for x in base if n(x) not in remove_set]


def parse_aaai_enriched(row: dict[str, str]) -> dict[str, Any]:
    obj = parse_json_maybe(row.get("enriched", ""), {})
    if not isinstance(obj, dict):
        return {}
    return obj


def org_blob(row: dict[str, str]) -> str:
    return n(f"{clean_text(row.get('所属机构（主要）', ''))} {clean_text(row.get('所属机构（全部）', ''))}")


def org_match(university: str, blob: str) -> bool:
    key_uni = n(university)
    return bool(key_uni and blob and (key_uni in blob or blob in key_uni))


def build_indices(
    rows: list[dict[str, Any]],
) -> tuple[
    dict[tuple[str, str], list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, dict[str, Any]],
]:
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    by_name_en: dict[str, list[dict[str, Any]]] = {}
    by_id: dict[str, dict[str, Any]] = {}

    for r in rows:
        sid = str(r.get("id") or "").strip()
        if not sid:
            continue
        by_id[sid] = r
        key_pair = (n(r.get("name")), n(r.get("university")))
        by_pair.setdefault(key_pair, []).append(r)

        key_name = n(r.get("name"))
        if key_name:
            by_name.setdefault(key_name, []).append(r)

        key_name_en = n(r.get("name_en"))
        if key_name_en:
            by_name_en.setdefault(key_name_en, []).append(r)

    return by_pair, by_name, by_name_en, by_id


def resolve_mentor_university_for_aaai_row(
    row: dict[str, str],
    mentor_name_to_unis: dict[str, list[str]],
) -> str | None:
    name_cn = clean_text(row.get("姓名（中文）", ""))
    if not name_cn:
        return None

    key_name = n(name_cn)
    uni_candidates = mentor_name_to_unis.get(key_name, [])
    if not uni_candidates:
        return None

    blob = org_blob(row)
    if len(uni_candidates) == 1:
        uni = uni_candidates[0]
        return uni if org_match(uni, blob) else None

    hits = [u for u in uni_candidates if org_match(u, blob)]
    if not hits:
        return None

    # Pick the most specific matched university string.
    return sorted(hits, key=lambda x: len(n(x)), reverse=True)[0]


async def connect_pool() -> None:
    await init_postgres_pool_from_settings()


async def run(apply_changes: bool) -> None:
    basic_rows_raw = load_csv(BASIC_CSV)
    aaai_rows = load_csv(AAAI_CSV)

    # Deduplicate basic mentor rows by (name, university), merge non-empty fields.
    mentor_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for row in basic_rows_raw:
        name = clean_text(row.get("导师姓名", ""))
        uni = clean_text(row.get("所属高校", ""))
        if not name or not uni:
            continue
        key = (n(name), n(uni))
        if key not in mentor_rows:
            mentor_rows[key] = {
                "name": name,
                "university": uni,
                "position": clean_text(row.get("职称", "")),
                "email": clean_email(row.get("邮箱", "")),
                "subtables": set([clean_text(row.get("子表", ""))]) if clean_text(row.get("子表", "")) else set(),
            }
            continue

        current = mentor_rows[key]
        pos = clean_text(row.get("职称", ""))
        em = clean_email(row.get("邮箱", ""))
        sub = clean_text(row.get("子表", ""))
        if pos and not clean_text(current.get("position")):
            current["position"] = pos
        if em and not clean_text(current.get("email")):
            current["email"] = em
        if sub:
            current["subtables"].add(sub)

    mentor_name_to_unis: dict[str, list[str]] = {}
    for m in mentor_rows.values():
        mentor_name_to_unis.setdefault(n(m["name"]), []).append(m["university"])

    await connect_pool()

    pool = get_postgres_pool()
    async with pool.acquire() as conn:
        db_rows_raw = await conn.fetch(
            """
            SELECT
              id, name, name_en, university, position, email, bio,
              adjunct_supervisor, project_category, project_subcategory,
              tags, custom_fields, source_id, updated_at,
              google_scholar_url, profile_url, lab_url, research_areas
            FROM scholars
            """
        )
        db_rows: list[dict[str, Any]] = [dict(r) for r in db_rows_raw]

        by_pair, by_name, by_name_en, by_id = build_indices(db_rows)

        stage1_stats = {
            "total_mentor_pairs": len(mentor_rows),
            "matched_exact": 0,
            "matched_contains": 0,
            "matched_hash_id": 0,
            "inserted": 0,
            "updated": 0,
            "unchanged": 0,
        }
        pair_to_scholar_id: dict[tuple[str, str], str] = {}

        async def exec_insert_stage1(record: dict[str, Any]) -> None:
            await conn.execute(
                """
                INSERT INTO scholars (
                  id, name, name_en, university, position, email, bio,
                  adjunct_supervisor, project_category, project_subcategory,
                  tags, custom_fields, source_id, research_areas,
                  profile_url, google_scholar_url
                ) VALUES (
                  $1, $2, $3, $4, $5, $6, $7,
                  $8::jsonb, $9, $10,
                  $11::text[], $12::jsonb, $13, $14::text[],
                  $15, $16
                )
                """,
                record["id"],
                clean_text(record.get("name")) or None,
                clean_text(record.get("name_en")) or None,
                clean_text(record.get("university")) or None,
                clean_text(record.get("position")) or None,
                clean_text(record.get("email")) or None,
                clean_text(record.get("bio")) or None,
                json.dumps(record.get("adjunct_supervisor") or {}, ensure_ascii=False),
                clean_text(record.get("project_category")) or "",
                clean_text(record.get("project_subcategory")) or "",
                list(record.get("tags") or []),
                json.dumps(record.get("custom_fields") or {}, ensure_ascii=False),
                clean_text(record.get("source_id")) or None,
                list(record.get("research_areas") or []),
                clean_text(record.get("profile_url")) or None,
                clean_text(record.get("google_scholar_url")) or None,
            )

        async def exec_update_stage1(record: dict[str, Any]) -> None:
            await conn.execute(
                """
                UPDATE scholars
                SET
                  university = $2,
                  position = $3,
                  email = $4,
                  adjunct_supervisor = $5::jsonb,
                  project_category = $6,
                  project_subcategory = $7,
                  tags = $8::text[],
                  custom_fields = $9::jsonb,
                  updated_at = now()
                WHERE id = $1
                """,
                record["id"],
                clean_text(record.get("university")) or None,
                clean_text(record.get("position")) or None,
                clean_text(record.get("email")) or None,
                json.dumps(record.get("adjunct_supervisor") or {}, ensure_ascii=False),
                clean_text(record.get("project_category")) or "",
                clean_text(record.get("project_subcategory")) or "",
                list(record.get("tags") or []),
                json.dumps(record.get("custom_fields") or {}, ensure_ascii=False),
            )

        for key, mentor in sorted(mentor_rows.items(), key=lambda x: (x[1]["university"], x[1]["name"])):
            name = mentor["name"]
            university = mentor["university"]
            key_name = n(name)
            key_uni = n(university)

            target: dict[str, Any] | None = None
            exact_rows = by_pair.get((key_name, key_uni), [])
            if exact_rows:
                target = pick_best(exact_rows)
                stage1_stats["matched_exact"] += 1
            else:
                name_rows = by_name.get(key_name, [])
                contains_rows = [
                    r
                    for r in name_rows
                    if key_uni and n(r.get("university")) and (key_uni in n(r.get("university")) or n(r.get("university")) in key_uni)
                ]
                if contains_rows:
                    target = pick_best(contains_rows)
                    stage1_stats["matched_contains"] += 1
                else:
                    hid = mentor_hash_id(name, university)
                    if hid in by_id:
                        target = by_id[hid]
                        stage1_stats["matched_hash_id"] += 1

            if target is None:
                new_id = mentor_hash_id(name, university)
                custom_fields = {
                    "education_training_adjunct": True,
                    "mentor_is_school_mentor": True,
                    "mentor_source_files": ["学院导师信息.csv"],
                    "mentor_subtables": sorted(list(mentor["subtables"])),
                }
                new_record = {
                    "id": new_id,
                    "name": name,
                    "name_en": "",
                    "university": university,
                    "position": mentor.get("position", ""),
                    "email": mentor.get("email", ""),
                    "bio": "",
                    "adjunct_supervisor": normalize_adjunct({}),
                    "project_category": EDU_CATEGORY,
                    "project_subcategory": MENTOR_SUBCATEGORY,
                    "tags": merge_tags([], MENTOR_TAGS),
                    "custom_fields": custom_fields,
                    "source_id": "mentor_import_csv",
                    "research_areas": [],
                    "profile_url": "",
                    "google_scholar_url": "",
                }
                if apply_changes:
                    await exec_insert_stage1(new_record)
                db_rows.append(new_record)
                by_pair, by_name, by_name_en, by_id = build_indices(db_rows)
                pair_to_scholar_id[(key_name, key_uni)] = new_id
                stage1_stats["inserted"] += 1
                continue

            record = dict(target)
            changed = False

            # Required by request: import name/org/position/email from basic mentor CSV.
            if clean_text(record.get("university")) != university:
                record["university"] = university
                changed = True

            pos = clean_text(mentor.get("position", ""))
            if pos and clean_text(record.get("position")) != pos:
                record["position"] = pos
                changed = True

            em = clean_email(mentor.get("email", ""))
            if em and clean_email(record.get("email", "")) != em:
                record["email"] = em
                changed = True

            raw_adjunct = record.get("adjunct_supervisor")
            adjunct = normalize_adjunct(raw_adjunct)
            record["adjunct_supervisor"] = adjunct
            if isinstance(raw_adjunct, str) or parse_json_maybe(raw_adjunct, {}) != adjunct:
                changed = True

            if clean_text(record.get("project_category")) != EDU_CATEGORY:
                record["project_category"] = EDU_CATEGORY
                changed = True
            if clean_text(record.get("project_subcategory")) != MENTOR_SUBCATEGORY:
                record["project_subcategory"] = MENTOR_SUBCATEGORY
                changed = True

            # School mentors should keep mentor tags; AAAI community tags are for non-mentor rows.
            merged_tags = merge_tags(remove_tags(record.get("tags"), AAAI_COMMUNITY_TAGS), MENTOR_TAGS)
            if merged_tags != to_list_text(record.get("tags")):
                record["tags"] = merged_tags
                changed = True

            custom_fields = parse_json_maybe(record.get("custom_fields"), {})
            if not isinstance(custom_fields, dict):
                custom_fields = {}
            record["custom_fields"] = custom_fields
            old_custom = json.dumps(custom_fields, ensure_ascii=False, sort_keys=True)

            custom_fields["education_training_adjunct"] = True
            custom_fields["mentor_is_school_mentor"] = True
            custom_fields.pop("aaai_community_member", None)
            custom_fields.pop("community_name", None)
            custom_fields.pop("community_type", None)
            custom_fields.pop("community_tags", None)

            sources = custom_fields.get("mentor_source_files")
            if not isinstance(sources, list):
                sources = []
            if "学院导师信息.csv" not in sources:
                sources.append("学院导师信息.csv")
            custom_fields["mentor_source_files"] = sources

            existing_subtables = custom_fields.get("mentor_subtables")
            if not isinstance(existing_subtables, list):
                existing_subtables = []
            custom_fields["mentor_subtables"] = sorted(
                list(set([clean_text(x) for x in existing_subtables if clean_text(x)] + list(mentor["subtables"])))
            )

            new_custom = json.dumps(custom_fields, ensure_ascii=False, sort_keys=True)
            if old_custom != new_custom:
                record["custom_fields"] = custom_fields
                changed = True

            if changed:
                if apply_changes:
                    await exec_update_stage1(record)
                stage1_stats["updated"] += 1
            else:
                stage1_stats["unchanged"] += 1

            # Sync in-memory indices after update.
            by_id[record["id"]] = record
            by_pair, by_name, by_name_en, by_id = build_indices(list(by_id.values()))
            pair_to_scholar_id[(key_name, key_uni)] = record["id"]

        # Stage 2: map AAAI+ CSV to mentor rows only.
        stage2_scan = {
            "aaai_total_rows": len(aaai_rows),
            "name_hit_rows": 0,
            "adjunct_candidate_rows": 0,
            "ambiguous_rows": 0,
            "no_pair_mapping_rows": 0,
            "resolved_pairs": 0,
            "updated": 0,
            "unchanged": 0,
        }

        best_aaai_by_pair: dict[tuple[str, str], dict[str, str]] = {}

        def aaai_score(row: dict[str, str]) -> int:
            fields = [
                row.get("姓名（英文）", ""),
                row.get("个人简介", ""),
                row.get("职位/职称", ""),
                row.get("邮箱", ""),
                row.get("谷歌学术主页", ""),
                row.get("网站个人主页", ""),
                row.get("研究方向", ""),
                row.get("教育经历", ""),
            ]
            return sum(1 for x in fields if clean_text(x))

        for row in aaai_rows:
            name_cn = clean_text(row.get("姓名（中文）", ""))
            if not name_cn:
                continue
            key_name = n(name_cn)
            if key_name not in mentor_name_to_unis:
                continue
            stage2_scan["name_hit_rows"] += 1

            resolved_uni = resolve_mentor_university_for_aaai_row(row, mentor_name_to_unis)
            if not resolved_uni:
                stage2_scan["ambiguous_rows"] += 1
                continue

            pair_key = (key_name, n(resolved_uni))
            if pair_key not in pair_to_scholar_id:
                stage2_scan["no_pair_mapping_rows"] += 1
                continue

            stage2_scan["adjunct_candidate_rows"] += 1
            prev = best_aaai_by_pair.get(pair_key)
            if prev is None or aaai_score(row) > aaai_score(prev):
                best_aaai_by_pair[pair_key] = row

        stage2_scan["resolved_pairs"] = len(best_aaai_by_pair)

        async def exec_update_stage2(record: dict[str, Any]) -> None:
            await conn.execute(
                """
                UPDATE scholars
                SET
                  name_en = $2,
                  bio = $3,
                  position = $4,
                  email = $5,
                  google_scholar_url = $6,
                  profile_url = $7,
                  research_areas = $8::text[],
                  custom_fields = $9::jsonb,
                  updated_at = now()
                WHERE id = $1
                """,
                record["id"],
                clean_text(record.get("name_en")) or None,
                clean_text(record.get("bio")) or None,
                clean_text(record.get("position")) or None,
                clean_text(record.get("email")) or None,
                clean_text(record.get("google_scholar_url")) or None,
                clean_text(record.get("profile_url")) or None,
                list(record.get("research_areas") or []),
                json.dumps(record.get("custom_fields") or {}, ensure_ascii=False),
            )

        for pair_key, row in best_aaai_by_pair.items():
            sid = pair_to_scholar_id[pair_key]
            base = by_id.get(sid)
            if not base:
                stage2_scan["no_pair_mapping_rows"] += 1
                continue

            record = dict(base)
            changed = False
            enriched = parse_aaai_enriched(row)

            name_en = clean_text(row.get("姓名（英文）", ""))
            if name_en and not clean_text(record.get("name_en")):
                record["name_en"] = name_en
                changed = True

            bio = clean_text(row.get("个人简介", ""))
            if bio and not clean_text(record.get("bio")):
                record["bio"] = bio
                changed = True

            pos = clean_text(row.get("职位/职称", ""))
            if pos and not clean_text(record.get("position")):
                record["position"] = pos
                changed = True

            email = clean_email(row.get("邮箱", ""))
            if not email:
                emails = enriched.get("emails")
                if isinstance(emails, list):
                    for em in emails:
                        candidate = clean_email(em)
                        if candidate and "@" in candidate:
                            email = candidate
                            break
            if email and "@" in email and not clean_email(record.get("email", "")):
                record["email"] = email
                changed = True

            gs_url = clean_text(row.get("谷歌学术主页", "")) or clean_text(enriched.get("google_scholar", ""))
            if gs_url and not clean_text(record.get("google_scholar_url")):
                record["google_scholar_url"] = gs_url
                changed = True

            home = clean_text(row.get("网站个人主页", "")) or clean_text(enriched.get("homepage", ""))
            if home and not clean_text(record.get("profile_url")):
                record["profile_url"] = home
                changed = True

            existing_areas = to_list_text(record.get("research_areas"))
            incoming_areas = to_list_text(row.get("研究方向", ""))
            if not incoming_areas:
                tags = enriched.get("research_tags")
                if isinstance(tags, list):
                    incoming_areas = [clean_text(t) for t in tags if clean_text(t)]
            merged_areas = merge_unique_text_list(existing_areas, incoming_areas)
            if merged_areas != existing_areas:
                record["research_areas"] = merged_areas
                changed = True

            custom_fields = parse_json_maybe(record.get("custom_fields"), {})
            if not isinstance(custom_fields, dict):
                custom_fields = {}
            record["custom_fields"] = custom_fields
            old_custom = json.dumps(custom_fields, ensure_ascii=False, sort_keys=True)

            custom_fields["aaai_plus_adjunct_mapped"] = True
            custom_fields["aaai_plus_org_main"] = clean_text(row.get("所属机构（主要）", ""))
            custom_fields["aaai_plus_org_all"] = clean_text(row.get("所属机构（全部）", ""))
            edu = clean_text(row.get("教育经历", ""))
            if edu:
                custom_fields["aaai_plus_education"] = edu

            new_custom = json.dumps(custom_fields, ensure_ascii=False, sort_keys=True)
            if old_custom != new_custom:
                record["custom_fields"] = custom_fields
                changed = True

            if changed:
                if apply_changes:
                    await exec_update_stage2(record)
                by_id[sid] = record
                stage2_scan["updated"] += 1
            else:
                stage2_scan["unchanged"] += 1

        # Rebuild indices after stage2 updates.
        by_pair, by_name, by_name_en, by_id = build_indices(list(by_id.values()))

        # Stage 3: non-mentor AAAI community scholars.
        stage3_stats = {
            "aaai_total_rows": len(aaai_rows),
            "mentor_rows_skipped": 0,
            "candidate_rows": 0,
            "resolved_existing": 0,
            "inserted": 0,
            "updated": 0,
            "unchanged": 0,
        }

        async def exec_update_stage3(record: dict[str, Any]) -> None:
            await conn.execute(
                """
                UPDATE scholars
                SET
                  name_en = $2,
                  bio = $3,
                  position = $4,
                  email = $5,
                  google_scholar_url = $6,
                  profile_url = $7,
                  research_areas = $8::text[],
                  tags = $9::text[],
                  custom_fields = $10::jsonb,
                  updated_at = now()
                WHERE id = $1
                """,
                record["id"],
                clean_text(record.get("name_en")) or None,
                clean_text(record.get("bio")) or None,
                clean_text(record.get("position")) or None,
                clean_text(record.get("email")) or None,
                clean_text(record.get("google_scholar_url")) or None,
                clean_text(record.get("profile_url")) or None,
                list(record.get("research_areas") or []),
                list(record.get("tags") or []),
                json.dumps(record.get("custom_fields") or {}, ensure_ascii=False),
            )

        for row in aaai_rows:
            # Exclude rows that are mentor rows in this import context.
            if resolve_mentor_university_for_aaai_row(row, mentor_name_to_unis):
                stage3_stats["mentor_rows_skipped"] += 1
                continue

            name_cn = clean_text(row.get("姓名（中文）", ""))
            name_en = clean_text(row.get("姓名（英文）", ""))
            if not name_cn and not name_en:
                continue

            stage3_stats["candidate_rows"] += 1
            enriched = parse_aaai_enriched(row)
            blob = org_blob(row)

            candidates: list[dict[str, Any]] = []
            seen_ids: set[str] = set()

            for idx in [by_name.get(n(name_cn), []), by_name.get(n(name_en), []), by_name_en.get(n(name_en), [])]:
                for cand in idx:
                    sid = str(cand.get("id") or "")
                    if sid and sid not in seen_ids:
                        seen_ids.add(sid)
                        candidates.append(cand)

            def cand_score(c: dict[str, Any]) -> tuple[int, int, int, int]:
                return (
                    1 if org_match(str(c.get("university") or ""), blob) else 0,
                    1 if clean_text(c.get("email")) else 0,
                    1 if clean_text(c.get("bio")) else 0,
                    1 if clean_text(c.get("updated_at")) else 0,
                )

            target: dict[str, Any] | None = max(candidates, key=cand_score) if candidates else None
            if target is not None:
                stage3_stats["resolved_existing"] += 1

            if target is None:
                new_id = aaai_hash_id(
                    name=name_cn,
                    name_en=name_en,
                    org_main=clean_text(row.get("所属机构（主要）", "")),
                    org_all=clean_text(row.get("所属机构（全部）", "")),
                )

                if new_id in by_id:
                    target = by_id[new_id]
                else:
                    incoming_areas = to_list_text(row.get("研究方向", ""))
                    if not incoming_areas:
                        rt = enriched.get("research_tags")
                        if isinstance(rt, list):
                            incoming_areas = [clean_text(t) for t in rt if clean_text(t)]

                    email = clean_email(row.get("邮箱", ""))
                    if not email:
                        emails = enriched.get("emails")
                        if isinstance(emails, list):
                            for em in emails:
                                candidate = clean_email(em)
                                if candidate and "@" in candidate:
                                    email = candidate
                                    break

                    custom_fields = {
                        "aaai_community_member": True,
                        "community_name": AAAI_COMMUNITY_NAME,
                        "community_type": AAAI_COMMUNITY_TYPE,
                        "community_tags": [AAAI_COMMUNITY_NAME, AAAI_COMMUNITY_TYPE],
                        "aaai_plus_org_main": clean_text(row.get("所属机构（主要）", "")),
                        "aaai_plus_org_all": clean_text(row.get("所属机构（全部）", "")),
                        "mentor_source_files": ["AAAI+学院导师.csv"],
                    }
                    edu = clean_text(row.get("教育经历", ""))
                    if edu:
                        custom_fields["aaai_plus_education"] = edu

                    new_record = {
                        "id": new_id,
                        "name": name_cn or name_en,
                        "name_en": name_en if name_cn else "",
                        "university": clean_text(row.get("所属机构（主要）", "")) or clean_text(row.get("所属机构（全部）", "")),
                        "position": clean_text(row.get("职位/职称", "")),
                        "email": email,
                        "bio": clean_text(row.get("个人简介", "")),
                        "adjunct_supervisor": empty_adjunct(),
                        "project_category": "",
                        "project_subcategory": "",
                        "tags": merge_tags([], AAAI_COMMUNITY_TAGS),
                        "custom_fields": custom_fields,
                        "source_id": "aaai_community_import",
                        "research_areas": incoming_areas,
                        "profile_url": clean_text(row.get("网站个人主页", "")) or clean_text(enriched.get("homepage", "")),
                        "google_scholar_url": clean_text(row.get("谷歌学术主页", "")) or clean_text(enriched.get("google_scholar", "")),
                    }

                    if apply_changes:
                        await exec_insert_stage1(new_record)
                    by_id[new_id] = new_record
                    by_pair, by_name, by_name_en, by_id = build_indices(list(by_id.values()))
                    stage3_stats["inserted"] += 1
                    continue

            record = dict(target)
            changed = False

            in_name_en = clean_text(name_en)
            if in_name_en and not clean_text(record.get("name_en")):
                record["name_en"] = in_name_en
                changed = True

            in_bio = clean_text(row.get("个人简介", ""))
            if in_bio and not clean_text(record.get("bio")):
                record["bio"] = in_bio
                changed = True

            in_pos = clean_text(row.get("职位/职称", ""))
            if in_pos and not clean_text(record.get("position")):
                record["position"] = in_pos
                changed = True

            in_email = clean_email(row.get("邮箱", ""))
            if not in_email:
                emails = enriched.get("emails")
                if isinstance(emails, list):
                    for em in emails:
                        candidate = clean_email(em)
                        if candidate and "@" in candidate:
                            in_email = candidate
                            break
            if in_email and "@" in in_email and not clean_email(record.get("email", "")):
                record["email"] = in_email
                changed = True

            gs_url = clean_text(row.get("谷歌学术主页", "")) or clean_text(enriched.get("google_scholar", ""))
            if gs_url and not clean_text(record.get("google_scholar_url")):
                record["google_scholar_url"] = gs_url
                changed = True

            home = clean_text(row.get("网站个人主页", "")) or clean_text(enriched.get("homepage", ""))
            if home and not clean_text(record.get("profile_url")):
                record["profile_url"] = home
                changed = True

            existing_areas = to_list_text(record.get("research_areas"))
            incoming_areas = to_list_text(row.get("研究方向", ""))
            if not incoming_areas:
                rt = enriched.get("research_tags")
                if isinstance(rt, list):
                    incoming_areas = [clean_text(t) for t in rt if clean_text(t)]
            merged_areas = merge_unique_text_list(existing_areas, incoming_areas)
            if merged_areas != existing_areas:
                record["research_areas"] = merged_areas
                changed = True

            merged_tags = merge_tags(record.get("tags"), AAAI_COMMUNITY_TAGS)
            if merged_tags != to_list_text(record.get("tags")):
                record["tags"] = merged_tags
                changed = True

            custom_fields = parse_json_maybe(record.get("custom_fields"), {})
            if not isinstance(custom_fields, dict):
                custom_fields = {}
            record["custom_fields"] = custom_fields
            old_custom = json.dumps(custom_fields, ensure_ascii=False, sort_keys=True)

            custom_fields["aaai_community_member"] = True
            custom_fields["community_name"] = AAAI_COMMUNITY_NAME
            custom_fields["community_type"] = AAAI_COMMUNITY_TYPE
            custom_fields["community_tags"] = merge_unique_text_list(
                to_list_text(custom_fields.get("community_tags")),
                [AAAI_COMMUNITY_NAME, AAAI_COMMUNITY_TYPE],
                limit=10,
            )
            custom_fields["aaai_plus_org_main"] = clean_text(row.get("所属机构（主要）", ""))
            custom_fields["aaai_plus_org_all"] = clean_text(row.get("所属机构（全部）", ""))

            source_files = custom_fields.get("mentor_source_files")
            if not isinstance(source_files, list):
                source_files = []
            if "AAAI+学院导师.csv" not in source_files:
                source_files.append("AAAI+学院导师.csv")
            custom_fields["mentor_source_files"] = source_files

            edu = clean_text(row.get("教育经历", ""))
            if edu:
                custom_fields["aaai_plus_education"] = edu

            new_custom = json.dumps(custom_fields, ensure_ascii=False, sort_keys=True)
            if old_custom != new_custom:
                record["custom_fields"] = custom_fields
                changed = True

            if changed:
                if apply_changes:
                    await exec_update_stage3(record)
                by_id[record["id"]] = record
                stage3_stats["updated"] += 1
            else:
                stage3_stats["unchanged"] += 1

        # Sync final index snapshot.
        by_pair, by_name, by_name_en, by_id = build_indices(list(by_id.values()))

    print("")
    print("===== Import Summary =====")
    print(f"Mode: {'APPLY' if apply_changes else 'DRY-RUN'}")
    print("")
    print("[Stage 1] 学院导师信息.csv")
    print(f"mentor pairs total: {stage1_stats['total_mentor_pairs']}")
    print(f"matched exact pair: {stage1_stats['matched_exact']}")
    print(f"matched by name+org contain: {stage1_stats['matched_contains']}")
    print(f"matched existing hash id: {stage1_stats['matched_hash_id']}")
    print(f"inserted: {stage1_stats['inserted']}")
    print(f"updated: {stage1_stats['updated']}")
    print(f"unchanged: {stage1_stats['unchanged']}")
    print("")
    print("[Stage 2] AAAI+学院导师.csv (mentor enrichment)")
    print(f"aaai rows total: {stage2_scan['aaai_total_rows']}")
    print(f"name hit rows (in mentor list): {stage2_scan['name_hit_rows']}")
    print(f"adjunct candidate rows: {stage2_scan['adjunct_candidate_rows']}")
    print(f"resolved mentor pairs: {stage2_scan['resolved_pairs']}")
    print(f"ambiguous rows skipped: {stage2_scan['ambiguous_rows']}")
    print(f"pair-mapping-miss rows skipped: {stage2_scan['no_pair_mapping_rows']}")
    print(f"updated: {stage2_scan['updated']}")
    print(f"unchanged: {stage2_scan['unchanged']}")
    print("")
    print("[Stage 3] AAAI community (non-mentor)")
    print(f"aaai rows total: {stage3_stats['aaai_total_rows']}")
    print(f"mentor rows skipped: {stage3_stats['mentor_rows_skipped']}")
    print(f"non-mentor candidate rows: {stage3_stats['candidate_rows']}")
    print(f"resolved existing scholars: {stage3_stats['resolved_existing']}")
    print(f"inserted: {stage3_stats['inserted']}")
    print(f"updated: {stage3_stats['updated']}")
    print(f"unchanged: {stage3_stats['unchanged']}")

    await close_postgres_pool()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import mentor/community data into scholars table")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview updates without writing")
    mode.add_argument("--apply", action="store_true", help="Apply changes to database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    apply_changes = bool(args.apply)
    asyncio.run(run(apply_changes=apply_changes))


if __name__ == "__main__":
    main()
