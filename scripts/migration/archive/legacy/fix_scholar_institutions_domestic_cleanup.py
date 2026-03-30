#!/usr/bin/env python3
"""Domestic university focused institution cleanup.

Legacy scope script. Prefer:
  .venv/bin/python scripts/migration/fix_scholar_institutions.py --scope global [--apply]

Goals:
1) Split concatenated "大学+院系" names in scholars.university into:
   - scholars.university: level-1 organization
   - scholars.department: level-2 department
2) Normalize short CAS institute aliases:
   - 自动化所 / 计算所 / 信工所 -> 中国科学院大学 + 对应研究所
3) Create missing institutions rows for changed records:
   - organization (if missing)
   - department (if missing)

Usage:
  .venv/bin/python scripts/migration/archive/legacy/fix_scholar_institutions_domestic_cleanup.py
  .venv/bin/python scripts/migration/archive/legacy/fix_scholar_institutions_domestic_cleanup.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import re
import unicodedata
from collections import Counter
from typing import Any

from app.config import settings
from app.db.pool import close_pool, get_pool, init_pool
from app.services.scholar._filters import (
    _derive_affiliation_type_from_university,
    _derive_region_from_university,
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
}

CAS_SHORT_MAP = {
    "自动化所": "自动化研究所",
    "计算所": "计算技术研究所",
    "信工所": "信息工程研究所",
}

TRAILING_TITLE_RE = re.compile(
    r"(?:教授|副教授|讲师|博士生|博士|硕士生|硕士|本科生|研究生|phd)$",
    re.IGNORECASE,
)
LEAD_SEP_RE = re.compile(r"^[\s,，;；:：|/\\\-—_()（）\[\]【】]+")
ROOT_CAPTURE_RE = re.compile(r"^(.{2,60}?大学(?:\(深圳\)|（深圳）)?)(.+)$")
DOMESTIC_UNI_NAME_RE = re.compile(r"^[\u4e00-\u9fff·\s()（）\-]{2,40}大学(?:\(深圳\)|（深圳）)?$")
INSTITUTION_END_RE = re.compile(
    r"(大学|学院|研究所|研究院|实验室|中心|Institute|University|College|Lab)$",
    re.IGNORECASE,
)

DEPT_HINT_RE = re.compile(
    r"(学院|学部|系|研究院|研究所|实验室|中心|研究中心|faculty|school|department|lab|institute|college)",
    re.IGNORECASE,
)
GENERIC_DEPT = {"学院", "学部", "系", "研究院", "研究所", "实验室", "中心", "研究中心"}

FOREIGN_MARKERS = (
    "美国",
    "英国",
    "德国",
    "法国",
    "意大利",
    "西班牙",
    "日本",
    "韩国",
    "新加坡",
    "澳大利亚",
    "加拿大",
    "以色列",
    "荷兰",
    "瑞士",
    "芬兰",
    "瑞典",
    "挪威",
    "丹麦",
    "比利时",
    "奥地利",
    "波兰",
    "罗马尼亚",
    "克罗地亚",
    "希腊",
    "阿布扎比",
    "伦敦",
    "纽约",
    "东京",
    "大阪",
    "京都",
    "苏黎世",
    "慕尼黑",
    "柏林",
    "巴黎",
    "哥本哈根",
    "墨尔本",
    "悉尼",
    "哈佛",
    "斯坦福",
    "麻省理工",
    "哥伦比亚",
    "普林斯顿",
    "耶鲁",
    "牛津",
    "剑桥",
    "伊利诺伊",
    "德克萨斯",
    "马萨诸塞",
    "威斯康星",
    "亚利桑那",
    "赫尔辛基",
    "多伦多",
    "卡内基梅隆",
    "莱斯",
    "芝加哥",
    "佛罗里达",
    "曼彻斯特",
    "伯明翰",
    "南洋",
    "首尔",
    "高丽",
    "延世",
    "麦吉尔",
    "乌得勒支",
    "博洛尼亚",
    "约翰·霍普金斯",
    "加州大学",
)

DOMESTIC_HINT_RE = re.compile(
    r"(北京|上海|天津|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|"
    r"河南|湖北|湖南|广东|海南|四川|贵州|云南|陕西|甘肃|青海|内蒙古|广西|"
    r"宁夏|新疆|香港|澳门)"
)

FORCED_DOMESTIC_UNIS = {
    "清华大学",
    "北京大学",
    "复旦大学",
    "浙江大学",
    "南京大学",
    "中国科学技术大学",
    "中国人民大学",
    "哈尔滨工业大学",
    "上海交通大学",
    "西安交通大学",
    "西北工业大学",
    "武汉大学",
    "厦门大学",
    "电子科技大学",
    "华中科技大学",
    "华南理工大学",
    "东南大学",
    "北京航空航天大学",
    "北京理工大学",
    "北京邮电大学",
    "北京交通大学",
    "北京师范大学",
    "北京科技大学",
    "合肥工业大学",
    "南京航空航天大学",
    "苏州大学",
    "江南大学",
    "暨南大学",
    "中国传媒大学",
    "中国地质大学",
    "中国矿业大学",
    "广东工业大学",
    "广州大学",
    "浙江工业大学",
    "杭州电子科技大学",
    "湖南大学",
    "山西大学",
    "云南大学",
    "昆明理工大学",
    "福州大学",
    "西南交通大学",
    "大连工业大学",
    "西湖大学",
}

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


def strip_trailing_location_like(text: str) -> str:
    s = clean_dept(text)
    if not s:
        return ""
    for sep_re in (r"[;；|]", r"[，,]"):
        parts = re.split(sep_re, s)
        if len(parts) <= 1:
            continue
        first = clean_dept(parts[0])
        if dept_like(first):
            s = first
    return clean_dept(s)


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


def has_multi_affiliation_markers(uni: str) -> bool:
    markers = (";", "；", "|", " / ", "/", ",", "，")
    return any(x in uni for x in markers) and not uni.startswith("中国科学院")


def starts_with_campus_prefix(suffix: str) -> bool:
    if any(suffix.startswith(p) for p in CAMPUS_PREFIX):
        return True
    if re.match(r"^.{1,8}分校", suffix):
        return True
    return False


def looks_foreign(name: str) -> bool:
    text = clean_text(name)
    return any(marker in text for marker in FOREIGN_MARKERS)


def should_apply_trimmed_uni(trimmed_uni: str) -> bool:
    if trimmed_uni in EXACT_UNI_MAP:
        return True
    return bool(INSTITUTION_END_RE.search(trimmed_uni))


def infer_domestic_root_candidates(
    org_rows: list[Any],
    standalone_uni_rows: list[Any],
) -> list[str]:
    roots: set[str] = set()

    for row in org_rows:
        name = clean_text(row["name"])
        if not name:
            continue
        if clean_text(row["org_type"]) != "高校":
            continue
        if clean_text(row["region"]) != "国内":
            continue
        if looks_foreign(name):
            continue
        roots.add(name)

    for row in standalone_uni_rows:
        name = clean_text(row["university"])
        if not name:
            continue
        if not DOMESTIC_UNI_NAME_RE.match(name):
            continue
        if looks_foreign(name):
            continue
        if not (DOMESTIC_HINT_RE.search(name) or name in FORCED_DOMESTIC_UNIS):
            continue
        roots.add(name)

    for value in EXACT_UNI_MAP.values():
        if value.endswith("大学"):
            roots.add(value)
    roots.update(FORCED_DOMESTIC_UNIS)

    return sorted(roots, key=lambda x: len(norm_key(x)), reverse=True)


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


def strip_leading_noise_for_root(uni: str, roots: list[str]) -> tuple[str, bool]:
    text = clean_text(uni)
    for root in roots:
        idx = text.find(root)
        if idx <= 0 or idx > 8:
            continue
        prefix = text[:idx]
        # Only strip obvious name-prefix noise like "王选 北京大学..."
        # Do not strip cross-institution prefixes like "苏黎世/西湖大学".
        if "/" in prefix or "／" in prefix:
            continue
        if ";" in prefix or "；" in prefix or "," in prefix or "，" in prefix:
            continue
        if len(norm_key(prefix)) <= 6 and re.search(r"\s", prefix):
            return text[idx:], True
    return text, False


def split_uni_and_dept_from_root(uni: str, root: str) -> tuple[str, str] | None:
    if not uni.startswith(root):
        return None
    if len(uni) <= len(root):
        return None
    suffix = clean_dept(uni[len(root):])
    suffix = re.sub(rf"[，,;；]\s*{re.escape(root)}\s*$", "", suffix)
    suffix = strip_trailing_location_like(suffix)
    if not suffix or starts_with_campus_prefix(suffix):
        return None
    if not dept_like(suffix):
        return None
    return root, suffix


async def main(apply: bool) -> None:
    if settings.POSTGRES_DSN:
        await init_pool(dsn=settings.POSTGRES_DSN)
    else:
        await init_pool(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
        )

    pool = get_pool()
    async with pool.acquire() as conn:
        org_rows = await conn.fetch(
            """
            SELECT id, name, region, org_type, type
            FROM institutions
            WHERE entity_type='organization' AND name IS NOT NULL AND BTRIM(name) <> ''
            """
        )
        standalone_uni_rows = await conn.fetch(
            """
            SELECT university, COUNT(*) AS c
            FROM scholars
            WHERE university IS NOT NULL
              AND BTRIM(university) <> ''
              AND university ~ '大学'
            GROUP BY university
            HAVING COUNT(*) >= 2
            """
        )
        scholar_rows = await conn.fetch(
            """
            SELECT id, university, department
            FROM scholars
            """
        )
        all_inst_ids = {
            str(x["id"])
            for x in await conn.fetch("SELECT id FROM institutions")
            if x["id"] is not None
        }

        domestic_roots = infer_domestic_root_candidates(org_rows, standalone_uni_rows)
        org_by_name: dict[str, dict[str, str]] = {}
        for row in org_rows:
            name = clean_text(row["name"])
            if not name:
                continue
            if name not in org_by_name:
                org_by_name[name] = {
                    "id": str(row["id"]),
                    "region": clean_text(row["region"]),
                    "org_type": clean_text(row["org_type"]),
                    "type": clean_text(row["type"]),
                }

        dept_rows = await conn.fetch(
            """
            SELECT id, parent_id, name
            FROM institutions
            WHERE entity_type='department' AND parent_id IS NOT NULL
            """
        )
        dept_key_set: set[tuple[str, str]] = set()
        for row in dept_rows:
            parent_id = str(row["parent_id"])
            name = clean_dept(row["name"])
            if parent_id and name:
                dept_key_set.add((parent_id, name))

        updates: list[tuple[str, str, str]] = []
        reason_counter: Counter[str] = Counter()
        sample_changes: list[str] = []

        for row in scholar_rows:
            sid = str(row["id"])
            old_uni = clean_text(row["university"])
            old_dept = clean_dept(row["department"])
            if not old_uni:
                continue

            uni = old_uni
            dept = old_dept
            reasons: list[str] = []

            trimmed_uni = TRAILING_TITLE_RE.sub("", uni).strip(" ,，;；:：")
            if trimmed_uni != uni and should_apply_trimmed_uni(trimmed_uni):
                uni = trimmed_uni
                reasons.append("trim_title")

            if uni in EXACT_UNI_MAP:
                uni = EXACT_UNI_MAP[uni]
                reasons.append("alias_exact")

            if uni in CAS_SHORT_MAP:
                dept = merge_dept(dept, CAS_SHORT_MAP[uni])
                uni = "中国科学院大学"
                reasons.append("cas_short_alias")

            cas_match = re.match(r"^(?:中国科学院|中科院)(.+?)(?:研究所|所)$", uni)
            if cas_match:
                body = clean_dept(cas_match.group(1))
                moved = body if body.endswith("研究所") else f"{body}研究所"
                dept = merge_dept(dept, moved)
                uni = "中国科学院大学"
                reasons.append("cas_institute_split")

            stripped_uni, stripped = strip_leading_noise_for_root(uni, domestic_roots)
            if stripped:
                uni = stripped_uni
                reasons.append("strip_leading_noise")

            matched = False
            test_uni = uni
            # Handle repeated suffix like "...，苏州大学" first.
            for root in domestic_roots:
                if not test_uni.startswith(root):
                    continue
                resolved = split_uni_and_dept_from_root(test_uni, root)
                if resolved:
                    uni = resolved[0]
                    dept = merge_dept(dept, resolved[1])
                    reasons.append("prefix_split_dept")
                    matched = True
                break

            if not matched and not has_multi_affiliation_markers(uni):
                m2 = ROOT_CAPTURE_RE.match(uni)
                if m2:
                    base = clean_text(m2.group(1))
                    suffix = strip_trailing_location_like(m2.group(2))
                    if (
                        base in domestic_roots
                        and not looks_foreign(base)
                        and not starts_with_campus_prefix(suffix)
                        and dept_like(suffix)
                    ):
                        uni = base
                        dept = merge_dept(dept, suffix)
                        reasons.append("regex_split_domestic")

            new_uni = clean_text(uni)
            new_dept = clean_dept(dept)
            if new_uni == old_uni and new_dept == old_dept:
                continue

            updates.append((sid, new_uni, new_dept))
            reason_key = "+".join(sorted(set(reasons))) or "cleanup"
            reason_counter[reason_key] += 1
            if len(sample_changes) < 60:
                sample_changes.append(
                    f"[{sid}] {reason_key}\n"
                    f"  UNI: {old_uni} -> {new_uni}\n"
                    f"  DEP: {old_dept} -> {new_dept}"
                )

        impacted_unis = sorted({u for _, u, _ in updates if u})
        impacted_depts = sorted({(u, d) for _, u, d in updates if u and d})

        print(f"domestic cleanup scholar updates candidate: {len(updates)}")
        for reason, cnt in reason_counter.most_common(30):
            print(f"  {cnt:>4} | {reason}")
        print("\nSample changes:")
        for line in sample_changes:
            print(line)
        print(f"\nimpacted universities: {len(impacted_unis)}")
        print(f"impacted departments: {len(impacted_depts)}")

        org_to_create: list[dict[str, str]] = []
        for uni in impacted_unis:
            if uni in org_by_name:
                continue
            is_domestic_uni = (
                (uni in domestic_roots)
                or (uni.endswith("大学") and not looks_foreign(uni))
            )
            if is_domestic_uni:
                region = "国内"
                org_type = "高校"
                inst_type = "university"
            else:
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
                    "type": org_meta.get("type") or "university",
                }
            )
            dept_key_set.add(key)

        print(f"organization rows to create: {len(org_to_create)}")
        if org_to_create:
            for row in org_to_create[:30]:
                print(f"  ORG {row['name']} | {row['region']} | {row['org_type']} | id={row['id']}")
        print(f"department rows to create: {len(dept_to_create)}")
        if dept_to_create:
            for row in dept_to_create[:30]:
                print(f"  DEP {row['name']} | parent={row['parent_id']} | id={row['id']}")

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

            impacted_org_names = [u for u in impacted_unis if u]
            for uni in impacted_org_names:
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
        print(f"  organizations created: {len(org_to_create)}")
        print(f"  departments created: {len(dept_to_create)}")

    await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Domestic scholar institution cleanup.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to DB. Without this flag runs in dry-run mode.",
    )
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
