#!/usr/bin/env python3
"""Global institution cleanup for scholar sidebar quality.

Canonical cleanup implementation. For unified entrypoint use:
  .venv/bin/python scripts/migration/fix_scholar_institutions.py --scope global [--apply]

Focus:
1) Merge noisy scholar.university values into organization (L1) + department (L2)
2) Reclassify obvious international organizations that are currently marked 国内
3) Create missing organization/department rows for merged results

Usage:
  .venv/bin/python scripts/migration/fix_scholar_institutions_region_and_merge.py
  .venv/bin/python scripts/migration/fix_scholar_institutions_region_and_merge.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.scholar._filters import (
    _derive_affiliation_type_from_university,
    _derive_region_from_university,
    _is_strong_intl_name,
)

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

EXACT_UNI_MAP = {
    "北航": "北京航空航天大学",
    "北航博士生": "北京航空航天大学",
    "北航教授": "北京航空航天大学",
    "北大": "北京大学",
    "清华": "清华大学",
    "北理工": "北京理工大学",
    "北邮": "北京邮电大学",
    "北交": "北京交通大学",
    "北师": "北京师范大学",
    "北科": "北京科技大学",
    "中科大": "中国科学技术大学",
    "上交大": "上海交通大学",
    "上交": "上海交通大学",
    "哈工大": "哈尔滨工业大学",
    "浙大": "浙江大学",
    "人大": "中国人民大学",
    "西工大": "西北工业大学",
    "西交": "西安交通大学",
    "新加坡国立": "新加坡国立大学",
    "南洋理工": "南洋理工大学",
    "帝国理工": "帝国理工学院",
    "哥大": "哥伦比亚大学",
    "宾大": "宾夕法尼亚大学",
    "斯坦福": "斯坦福大学",
    "哈佛": "哈佛大学",
    "牛津": "牛津大学",
    "剑桥": "剑桥大学",
}

EXACT_ORG_DEPT_MAP = {
    "谷歌深度思维": ("Google", "DeepMind"),
    "谷歌研究院": ("Google", "Research"),
    "微软研究院": ("Microsoft", "Research"),
}

CAS_SHORT_MAP = {
    "自动化所": "自动化研究所",
    "计算所": "计算技术研究所",
    "信工所": "信息工程研究所",
}

STATUS_SUFFIX_RE = re.compile(
    r"(?:博士在读|硕士在读|博士生|硕士生|博士后|博后|本科生|在读|就读phd|phd|"
    r"助理教授|副教授|教授|讲师|ap)$",
    re.IGNORECASE,
)
INSTITUTION_END_RE = re.compile(
    r"(大学|学院|研究所|研究院|实验室|中心|Institute|University|College|Lab|Company)$",
    re.IGNORECASE,
)
ROOT_CAPTURE_RE = re.compile(
    r"^(.{2,80}?大学(?:.{0,12}?分校)?(?:\(深圳\)|（深圳）)?)(.+)$"
)
LEAD_SEP_RE = re.compile(r"^[\s,，;；:：|/\\\-—_()（）\[\]【】]+")
DEPT_HINT_RE = re.compile(
    r"(学院|学部|系|研究院|研究所|实验室|中心|研究中心|faculty|school|department|lab|institute|college)",
    re.IGNORECASE,
)
GENERIC_DEPT = {"学院", "学部", "系", "研究院", "研究所", "实验室", "中心", "研究中心"}
CAMPUS_PREFIX = (
    "分校",
    "校区",
    "帕克分校",
    "厄巴纳",
    "洛杉矶分校",
    "圣地亚哥分校",
    "伯克利分校",
    "阿默斯特分校",
    "布法罗分校",
    "芝加哥分校",
    "圣克鲁斯分校",
    "默塞德分校",
    "戴维斯分校",
    "圣塔芭芭拉分校",
    "密西沙加分校",
    "(深圳)",
    "（深圳）",
    "深圳校区",
)

def clean_text(v: object) -> str:
    if v is None:
        return ""
    t = unicodedata.normalize("NFKC", str(v))
    t = t.replace("\u3000", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def norm_key(v: object) -> str:
    t = clean_text(v).lower()
    t = re.sub(r"[\s,，;；:：|/\\\-—_()（）\[\]【】'\"`·•.]+", "", t)
    return t


def clean_dept(v: object) -> str:
    t = clean_text(v)
    t = LEAD_SEP_RE.sub("", t)
    t = t.strip("，,;；:：|/\\-—_ ")
    return t


def dept_like(s: str) -> bool:
    s = clean_dept(s)
    if not s or s in GENERIC_DEPT or len(s) <= 2:
        return False
    return bool(DEPT_HINT_RE.search(s))


def merge_dept(old_dept: str, moved: str) -> str:
    o = clean_dept(old_dept)
    m = clean_dept(moved)
    if not m:
        return o
    if not o:
        return m
    if m in o:
        return o
    if o in m:
        return m
    return f"{o} / {m}"


def starts_with_campus_prefix(suffix: str) -> bool:
    if any(suffix.startswith(p) for p in CAMPUS_PREFIX):
        return True
    if re.match(r"^.{1,8}分校", suffix):
        return True
    return False


def pick_primary_affiliation(uni: str) -> tuple[str, bool]:
    text = clean_text(uni)
    for sep in ("；", ";", "|"):
        if sep not in text:
            continue
        first = clean_text(text.split(sep, 1)[0])
        if INSTITUTION_END_RE.search(first) or "大学" in first or "学院" in first or "公司" in first:
            return first, True
    return text, False


def trim_status_suffix(uni: str) -> tuple[str, bool]:
    text = clean_text(uni)
    trimmed = STATUS_SUFFIX_RE.sub("", text).strip(" ,，;；:：")
    if trimmed == text:
        return text, False
    return trimmed, True


def should_accept_trimmed(trimmed: str, root_key_set: set[str]) -> bool:
    if not trimmed:
        return False
    if trimmed in EXACT_UNI_MAP:
        return True
    if norm_key(trimmed) in root_key_set:
        return True
    if INSTITUTION_END_RE.search(trimmed):
        return True
    return False


def strip_trailing_repeat_root(suffix: str, root: str) -> str:
    s = clean_dept(suffix)
    s = re.sub(rf"[，,;；]\s*{re.escape(root)}\s*$", "", s)
    return clean_dept(s)


def strip_location_tail(suffix: str) -> str:
    s = clean_dept(suffix)
    if not s:
        return ""
    parts = re.split(r"[;；|]", s)
    if len(parts) > 1 and dept_like(parts[0]):
        s = clean_dept(parts[0])
    return s


def generate_institution_id(name: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "_", clean_text(name)).strip("_").lower()
    if not cleaned:
        cleaned = "institution"
    return cleaned[:50]


def ensure_unique_id(base_id: str, used_ids: set[str]) -> str:
    if base_id not in used_ids:
        used_ids.add(base_id)
        return base_id
    idx = 2
    while True:
        cand = f"{base_id}_{idx}"
        if cand not in used_ids:
            used_ids.add(cand)
            return cand
        idx += 1


def is_strong_intl_name(name: str) -> bool:
    return _is_strong_intl_name(name)


def normalize_university_department(
    *,
    university: str,
    department: str,
    sorted_roots: list[str],
    root_set: set[str],
    root_key_set: set[str],
) -> tuple[str, str, list[str]]:
    """Normalize university (L1) and department (L2) with shared split rules."""
    uni = clean_text(university)
    dept = clean_dept(department)
    reasons: list[str] = []

    if not uni:
        return uni, dept, reasons

    uni, picked = pick_primary_affiliation(uni)
    if picked:
        reasons.append("pick_primary_affiliation")

    if uni in EXACT_ORG_DEPT_MAP:
        mapped_uni, mapped_dept = EXACT_ORG_DEPT_MAP[uni]
        uni = mapped_uni
        dept = mapped_dept
        reasons.append("alias_exact_org_dept")

    if uni in EXACT_UNI_MAP:
        uni = EXACT_UNI_MAP[uni]
        reasons.append("alias_exact")

    trimmed_uni, trimmed = trim_status_suffix(uni)
    if trimmed and should_accept_trimmed(trimmed_uni, root_key_set):
        uni = trimmed_uni
        reasons.append("trim_status")

    if uni in EXACT_UNI_MAP:
        uni = EXACT_UNI_MAP[uni]
        reasons.append("alias_exact")

    if uni in CAS_SHORT_MAP or any(uni.startswith(x) for x in CAS_SHORT_MAP):
        matched = None
        for p, d in CAS_SHORT_MAP.items():
            if uni.startswith(p):
                matched = d
                break
        if matched:
            dept = merge_dept(dept, matched)
            uni = "中国科学院大学"
            reasons.append("cas_short_alias")

    cas_match = re.match(r"^(?:中国科学院|中科院)(.+?)(?:研究所|所)$", uni)
    if cas_match:
        body = clean_dept(cas_match.group(1))
        moved = body if body.endswith("研究所") else f"{body}研究所"
        dept = merge_dept(dept, moved)
        uni = "中国科学院大学"
        reasons.append("cas_institute_split")

    for root in sorted_roots:
        if not uni.startswith(root):
            continue
        if len(uni) <= len(root):
            continue
        suffix = clean_dept(uni[len(root):])
        suffix = strip_trailing_repeat_root(suffix, root)
        suffix = strip_location_tail(suffix)
        if not suffix:
            continue
        if starts_with_campus_prefix(suffix):
            continue
        if not dept_like(suffix):
            continue
        uni = root
        dept = merge_dept(dept, suffix)
        reasons.append("prefix_split_dept")
        break

    m = ROOT_CAPTURE_RE.match(uni)
    if m:
        base = clean_text(m.group(1))
        suffix = strip_location_tail(m.group(2))
        if (
            base in root_set
            and suffix
            and not starts_with_campus_prefix(suffix)
            and dept_like(suffix)
        ):
            uni = base
            dept = merge_dept(dept, suffix)
            reasons.append("regex_split_root")

    return clean_text(uni), clean_dept(dept), reasons


async def main(apply: bool, convert_org_rows: bool = True) -> None:
    await init_postgres_pool_from_settings()
    pool = get_postgres_pool()
    async with pool.acquire() as conn:
        org_rows = await conn.fetch(
            """
            SELECT id, name, region, org_type, type, COALESCE(scholar_count, 0) AS scholar_count
            FROM institutions
            WHERE entity_type='organization' AND name IS NOT NULL AND BTRIM(name) <> ''
            """
        )
        scholar_rows = await conn.fetch(
            """
            SELECT id, university, department
            FROM scholars
            """
        )
        freq_rows = await conn.fetch(
            """
            SELECT university, COUNT(*) AS c
            FROM scholars
            WHERE university IS NOT NULL AND BTRIM(university) <> ''
            GROUP BY university
            HAVING COUNT(*) >= 2
            """
        )
        dept_rows = await conn.fetch(
            """
            SELECT id, parent_id, name
            FROM institutions
            WHERE entity_type='department' AND parent_id IS NOT NULL
            """
        )
        all_inst_ids = {
            str(x["id"])
            for x in await conn.fetch("SELECT id FROM institutions")
            if x["id"] is not None
        }

        org_by_name: dict[str, dict[str, str]] = {}
        root_set: set[str] = set()
        split_root_set: set[str] = set()
        split_root_keyword_re = re.compile(
            r"(大学|学院|研究所|研究院|实验室|中心|公司|集团|Institute|University|College|Lab|Research)",
            re.IGNORECASE,
        )
        split_root_force_allow = {
            "华为",
            "腾讯",
            "阿里巴巴",
            "阿里",
            "百度",
            "字节跳动",
            "Google",
            "Meta",
            "IBM",
            "微软",
        }
        for row in org_rows:
            name = clean_text(row["name"])
            if not name:
                continue
            root_set.add(name)
            if (
                name in split_root_force_allow
                or split_root_keyword_re.search(name)
                or int(row["scholar_count"] or 0) >= 8
            ):
                split_root_set.add(name)
            if name not in org_by_name:
                org_by_name[name] = {
                    "id": str(row["id"]),
                    "region": clean_text(row["region"]),
                    "org_type": clean_text(row["org_type"]),
                    "type": clean_text(row["type"]),
                }

        # Promote frequent "pure root" universities as split candidates.
        for row in freq_rows:
            u = clean_text(row["university"])
            if not u:
                continue
            if not INSTITUTION_END_RE.search(u):
                continue
            if dept_like(u):
                # university-like names such as "伦敦大学学院" should still be roots
                if "大学" not in u and "学院" not in u:
                    continue
            root_set.add(u)
            split_root_set.add(u)

        for v in EXACT_UNI_MAP.values():
            root_set.add(v)
            split_root_set.add(v)

        sorted_roots = sorted(split_root_set, key=lambda s: len(norm_key(s)), reverse=True)
        root_key_set = {norm_key(x) for x in root_set if x}

        dept_key_set: set[tuple[str, str]] = set()
        for row in dept_rows:
            parent_id = str(row["parent_id"])
            name = clean_dept(row["name"])
            if parent_id and name:
                dept_key_set.add((parent_id, name))

        updates_by_id: dict[str, tuple[str, str]] = {}
        reason_counter: Counter[str] = Counter()
        sample_changes: list[str] = []
        scholar_rows_by_university: dict[str, list[dict]] = {}

        for row in scholar_rows:
            sid = str(row["id"])
            old_uni = clean_text(row["university"])
            old_dept = clean_dept(row["department"])
            if not old_uni:
                continue

            scholar_rows_by_university.setdefault(old_uni, []).append(dict(row))

            new_uni, new_dept, reasons = normalize_university_department(
                university=old_uni,
                department=old_dept,
                sorted_roots=sorted_roots,
                root_set=root_set,
                root_key_set=root_key_set,
            )
            if new_uni == old_uni and new_dept == old_dept:
                continue

            updates_by_id[sid] = (new_uni, new_dept)
            reason_key = "+".join(sorted(set(reasons))) or "cleanup"
            reason_counter[reason_key] += 1
            if len(sample_changes) < 80:
                sample_changes.append(
                    f"[{sid}] {reason_key}\n"
                    f"  UNI: {old_uni} -> {new_uni}\n"
                    f"  DEP: {old_dept} -> {new_dept}"
                )

        # Institution-table level L1/L2 normalization candidates.
        org_split_candidates: list[dict[str, str]] = []
        if convert_org_rows:
            for row in org_rows:
                iid = str(row["id"])
                old_name = clean_text(row["name"])
                if not old_name:
                    continue
                new_uni, moved_dept, reasons = normalize_university_department(
                    university=old_name,
                    department="",
                    sorted_roots=sorted_roots,
                    root_set=root_set,
                    root_key_set=root_key_set,
                )
                if not moved_dept:
                    continue
                if new_uni == old_name:
                    continue
                org_split_candidates.append(
                    {
                        "id": iid,
                        "old_name": old_name,
                        "new_uni": new_uni,
                        "new_dept": moved_dept,
                        "reason": "+".join(sorted(set(reasons))) or "org_split",
                    }
                )
                reason_counter["org_split_candidate"] += 1
                if len(sample_changes) < 80:
                    sample_changes.append(
                        f"[ORG:{iid}] {old_name} -> {new_uni} / {moved_dept}"
                    )

        # Align scholars that still reference split-able institution names.
        for candidate in org_split_candidates:
            old_uni = candidate["old_name"]
            new_uni = candidate["new_uni"]
            moved_dept = candidate["new_dept"]
            for row in scholar_rows_by_university.get(old_uni, []):
                sid = str(row["id"])
                base_uni, base_dept = updates_by_id.get(
                    sid,
                    (clean_text(row.get("university")), clean_dept(row.get("department"))),
                )
                if clean_text(base_uni) != old_uni:
                    continue
                updates_by_id[sid] = (new_uni, merge_dept(base_dept, moved_dept))
                reason_counter["org_row_split_align_scholar"] += 1

        updates: list[tuple[str, str, str]] = sorted(
            [(sid, uni, dept) for sid, (uni, dept) in updates_by_id.items()],
            key=lambda x: x[0],
        )

        impacted_uni_set: set[str] = {u for _, u, _ in updates if u}
        impacted_dept_set: set[tuple[str, str]] = {(u, d) for _, u, d in updates if u and d}
        for candidate in org_split_candidates:
            new_uni = candidate["new_uni"]
            new_dept = candidate["new_dept"]
            if new_uni:
                impacted_uni_set.add(new_uni)
            if new_uni and new_dept:
                impacted_dept_set.add((new_uni, new_dept))

        # Prepare organization creation for new L1 names.
        org_to_create: list[dict[str, str]] = []
        for uni in sorted(impacted_uni_set):
            if uni in org_by_name:
                continue
            region = _derive_region_from_university(uni)
            org_type = _derive_affiliation_type_from_university(uni)
            if org_type == "高校":
                inst_type = "university"
            elif org_type == "研究机构":
                inst_type = "research_institute"
            elif org_type == "企业":
                inst_type = "company"
            else:
                inst_type = "other"
            org_id = ensure_unique_id(generate_institution_id(uni), all_inst_ids)
            org_to_create.append(
                {
                    "id": org_id,
                    "name": uni,
                    "region": region,
                    "org_type": org_type,
                    "type": inst_type,
                }
            )
            org_by_name[uni] = {
                "id": org_id,
                "region": region,
                "org_type": org_type,
                "type": inst_type,
            }

        # Convert malformed L1 rows into L2 rows under canonical L1 organization.
        org_row_conversions: list[dict[str, str]] = []
        for candidate in org_split_candidates:
            old_id = candidate["id"]
            root_uni = candidate["new_uni"]
            moved_dept = candidate["new_dept"]
            root_meta = org_by_name.get(root_uni)
            if not root_meta:
                continue
            root_id = root_meta["id"]
            if root_id == old_id:
                continue

            target_dept_name = moved_dept
            dept_key = (root_id, target_dept_name)
            if dept_key in dept_key_set:
                suffix = 2
                target_dept_name = f"{moved_dept}（整合）"
                dept_key = (root_id, target_dept_name)
                while dept_key in dept_key_set:
                    target_dept_name = f"{moved_dept}（整合{suffix}）"
                    dept_key = (root_id, target_dept_name)
                    suffix += 1
            dept_key_set.add(dept_key)
            impacted_dept_set.add((root_uni, target_dept_name))
            org_row_conversions.append(
                {
                    "id": old_id,
                    "name": target_dept_name,
                    "parent_id": root_id,
                    "region": root_meta.get("region") or _derive_region_from_university(root_uni),
                    "org_type": root_meta.get("org_type") or _derive_affiliation_type_from_university(root_uni),
                }
            )
            reason_counter["org_row_to_department"] += 1

        conversion_ids = {item["id"] for item in org_row_conversions}
        impacted_unis = sorted(impacted_uni_set)
        impacted_depts = sorted(impacted_dept_set)

        # Prepare department creation.
        dept_to_create: list[dict[str, str]] = []
        for uni, dept in impacted_depts:
            org_meta = org_by_name.get(uni)
            if not org_meta:
                continue
            parent_id = org_meta["id"]
            key = (parent_id, dept)
            if key in dept_key_set:
                continue
            dept_id = ensure_unique_id(
                f"{parent_id}_{generate_institution_id(dept)}"[:110],
                all_inst_ids,
            )
            dept_to_create.append(
                {
                    "id": dept_id,
                    "name": dept,
                    "parent_id": parent_id,
                    "region": org_meta.get("region") or _derive_region_from_university(uni),
                    "org_type": org_meta.get("org_type") or _derive_affiliation_type_from_university(uni),
                    "type": org_meta.get("type") or "other",
                }
            )
            dept_key_set.add(key)

        # Region fixes for existing organizations: only domestic->international
        # when strong international markers are present.
        region_fix_rows: list[tuple[str, str, str, str]] = []
        for row in org_rows:
            iid = str(row["id"])
            if iid in conversion_ids:
                continue
            name = clean_text(row["name"])
            old_region = clean_text(row["region"])
            old_org_type = clean_text(row["org_type"])
            new_region = old_region
            new_org_type = old_org_type

            # Conservative: only force obvious international corrections.
            if old_region == "国内" and is_strong_intl_name(name):
                new_region = "国际"
            elif not old_region and is_strong_intl_name(name):
                new_region = "国际"

            if (not old_org_type) and is_strong_intl_name(name):
                new_org_type = _derive_affiliation_type_from_university(name)

            if new_region != old_region or new_org_type != old_org_type:
                region_fix_rows.append((iid, new_region, new_org_type, name))

        print(f"global cleanup scholar updates candidate: {len(updates)}")
        for reason, cnt in reason_counter.most_common(30):
            print(f"  {cnt:>4} | {reason}")
        print("\nSample scholar changes:")
        for line in sample_changes:
            print(line)
        print(f"\nimpacted universities: {len(impacted_unis)}")
        print(f"impacted departments: {len(impacted_depts)}")
        print(f"organization split candidates: {len(org_split_candidates)}")
        print(f"organization rows to convert to departments: {len(org_row_conversions)}")
        print(f"organization rows to create: {len(org_to_create)}")
        print(f"department rows to create: {len(dept_to_create)}")
        print(f"organization region/meta fixes: {len(region_fix_rows)}")
        for _, region, org_type, name in region_fix_rows[:50]:
            print(f"  FIX {name} -> region={region}, org_type={org_type}")

        if not apply:
            return

        async with conn.transaction():
            for sid, new_uni, new_dept in updates:
                await conn.execute(
                    """
                    UPDATE scholars
                    SET university=$2, department=$3
                    WHERE id=$1
                    """,
                    sid,
                    new_uni or None,
                    new_dept or None,
                )

            for row in org_to_create:
                await conn.execute(
                    """
                    INSERT INTO institutions (
                        id, name, entity_type, type, region, org_type, parent_id, scholar_count, mentor_count, priority
                    ) VALUES ($1, $2, 'organization', $3, $4, $5, NULL, 0, 0, 3)
                    """,
                    row["id"],
                    row["name"],
                    row["type"],
                    row["region"] or None,
                    row["org_type"] or None,
                )

            for row in org_row_conversions:
                await conn.execute(
                    """
                    UPDATE institutions
                    SET parent_id=$2
                    WHERE entity_type='department' AND parent_id=$1
                    """,
                    row["id"],
                    row["parent_id"],
                )
                await conn.execute(
                    """
                    UPDATE institutions
                    SET name=$2,
                        entity_type='department',
                        type='department',
                        region=$3,
                        org_type=$4,
                        parent_id=$5,
                        priority=3
                    WHERE id=$1
                    """,
                    row["id"],
                    row["name"],
                    row["region"] or None,
                    row["org_type"] or None,
                    row["parent_id"],
                )

            for row in dept_to_create:
                await conn.execute(
                    """
                    INSERT INTO institutions (
                        id, name, entity_type, type, region, org_type, parent_id, scholar_count, mentor_count, priority
                    ) VALUES ($1, $2, 'department', $3, $4, $5, $6, 0, 0, 3)
                    """,
                    row["id"],
                    row["name"],
                    row["type"],
                    row["region"] or None,
                    row["org_type"] or None,
                    row["parent_id"],
                )

            for iid, new_region, new_org_type, _ in region_fix_rows:
                await conn.execute(
                    """
                    UPDATE institutions
                    SET region=$2, org_type=$3
                    WHERE id=$1
                    """,
                    iid,
                    new_region or None,
                    new_org_type or None,
                )

            # Recompute counts for impacted organizations/departments.
            for uni in impacted_unis:
                await conn.execute(
                    """
                    UPDATE institutions i
                    SET scholar_count = sub.cnt
                    FROM (
                        SELECT COUNT(*)::int AS cnt FROM scholars WHERE university=$1
                    ) sub
                    WHERE i.entity_type='organization' AND i.name=$1
                    """,
                    uni,
                )

            for uni, dept in impacted_depts:
                await conn.execute(
                    """
                    UPDATE institutions i
                    SET scholar_count = sub.cnt
                    FROM (
                        SELECT COUNT(*)::int AS cnt
                        FROM scholars
                        WHERE university=$1 AND department=$2
                    ) sub
                    WHERE i.entity_type='department'
                      AND i.parent_id = (
                          SELECT id FROM institutions
                          WHERE entity_type='organization' AND name=$1
                          ORDER BY id
                          LIMIT 1
                      )
                      AND i.name=$2
                    """,
                    uni,
                    dept,
                )

        print("\nAPPLY completed.")
        print(f"  scholars updated: {len(updates)}")
        print(f"  organization rows converted to departments: {len(org_row_conversions)}")
        print(f"  organizations created: {len(org_to_create)}")
        print(f"  departments created: {len(dept_to_create)}")
        print(f"  organizations region/meta fixed: {len(region_fix_rows)}")

    await close_postgres_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Global scholar institution cleanup.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to DB. Without this flag runs in dry-run mode.",
    )
    parser.add_argument(
        "--skip-org-row-conversion",
        action="store_true",
        help="Only clean scholar rows and region metadata, skip organization->department conversion.",
    )
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply, convert_org_rows=not args.skip_org_row_conversion))
